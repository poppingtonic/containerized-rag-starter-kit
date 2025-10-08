"""
Smart Ingestion Service

Automatically processes documents using unstructured-api and routes them
to appropriate knowledge stores based on document type and content.
"""

import os
import asyncio
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass
import hashlib
import logging

from .unstructured_client import UnstructuredClient, ProcessedDocument
from .document_router import (
    DocumentRouter,
    RoutingResult,
    is_meeting_document,
    is_email_document,
    is_presentation_document,
    is_spreadsheet_document,
    is_code_document
)
from ..stores.api_management import (
    StoreManagementAPI,
    CreateStoreRequest,
    IndexDocumentRequest
)


logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Result of document ingestion"""
    success: bool
    filename: str
    store_id: str
    doc_id: str
    num_chunks: int
    routing_info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time_seconds: Optional[float] = None


class SmartIngestionService:
    """
    Smart ingestion service that:
    1. Processes documents with unstructured-api
    2. Routes them to appropriate knowledge stores
    3. Auto-creates stores if needed
    4. Handles deduplication
    5. Tracks ingestion history

    Example usage:
        service = SmartIngestionService(
            unstructured_api_url="http://localhost:8001",
            store_management_api=store_api,
            router_config="/path/to/routing_rules.yaml"
        )

        result = await service.ingest_file(
            filepath="/path/to/document.pdf",
            metadata={"source": "email", "date": "2024-10-08"}
        )

        print(f"Ingested to store: {result.store_id}")
    """

    def __init__(
        self,
        unstructured_api_url: str,
        store_management_api: StoreManagementAPI,
        router_config: Optional[str] = None,
        default_store_id: str = "general_documents",
        auto_create_stores: bool = True,
        store_configs: Optional[Dict[str, Dict]] = None
    ):
        """
        Initialize smart ingestion service.

        Args:
            unstructured_api_url: URL of unstructured-api service
            store_management_api: StoreManagementAPI instance
            router_config: Path to routing rules YAML file
            default_store_id: Default store for unmatched documents
            auto_create_stores: Automatically create stores if they don't exist
            store_configs: Configuration for auto-created stores
        """
        self.unstructured_client = UnstructuredClient(api_url=unstructured_api_url)
        self.store_api = store_management_api
        self.router = DocumentRouter(config_path=router_config, default_store_id=default_store_id)
        self.auto_create_stores = auto_create_stores
        self.store_configs = store_configs or {}

        # Register custom routing functions
        self.router.register_custom_function("is_meeting_document", is_meeting_document)
        self.router.register_custom_function("is_email_document", is_email_document)
        self.router.register_custom_function("is_presentation_document", is_presentation_document)
        self.router.register_custom_function("is_spreadsheet_document", is_spreadsheet_document)
        self.router.register_custom_function("is_code_document", is_code_document)

        # Track processed files for deduplication
        self.processed_hashes: Dict[str, str] = {}  # hash -> doc_id

    async def ingest_file(
        self,
        filepath: str,
        metadata: Optional[Dict[str, Any]] = None,
        strategy: str = "auto",
        force_store_id: Optional[str] = None
    ) -> IngestionResult:
        """
        Ingest a single file.

        Args:
            filepath: Path to file
            metadata: Additional metadata for the document
            strategy: Unstructured processing strategy ("auto", "fast", "hi_res")
            force_store_id: Force routing to specific store (overrides rules)

        Returns:
            IngestionResult with ingestion details
        """
        import time
        start_time = time.time()

        filepath = Path(filepath)
        filename = filepath.name
        metadata = metadata or {}

        logger.info(f"Starting ingestion of {filename}")

        try:
            # 1. Check for duplicates
            content_hash = self._compute_file_hash(filepath)
            if content_hash in self.processed_hashes:
                logger.info(f"File {filename} already processed (duplicate)")
                return IngestionResult(
                    success=False,
                    filename=filename,
                    store_id="",
                    doc_id=self.processed_hashes[content_hash],
                    num_chunks=0,
                    error="Duplicate file already processed"
                )

            # 2. Process document with unstructured-api
            logger.info(f"Processing {filename} with unstructured-api (strategy: {strategy})")
            processed_doc = self.unstructured_client.process_file(
                filepath=filepath,
                strategy=strategy,
                pdf_infer_table_structure=True
            )

            # 3. Extract text content
            content = self.unstructured_client.extract_text(processed_doc)

            if not content.strip():
                logger.warning(f"No text content extracted from {filename}")
                return IngestionResult(
                    success=False,
                    filename=filename,
                    store_id="",
                    doc_id="",
                    num_chunks=0,
                    error="No text content extracted"
                )

            # 4. Route to appropriate store
            if force_store_id:
                routing = RoutingResult(
                    store_id=force_store_id,
                    rule_id="forced",
                    rule_name="Forced Routing",
                    confidence=1.0
                )
            else:
                logger.info(f"Routing {filename} to appropriate store")
                routing = self.router.route_document(
                    filename=filename,
                    content=content,
                    metadata=metadata
                )

            logger.info(f"Routed {filename} to store: {routing.store_id} (rule: {routing.rule_name})")

            # 5. Ensure store exists
            if self.auto_create_stores:
                await self._ensure_store_exists(routing.store_id)

            # 6. Prepare document metadata
            doc_metadata = {
                **metadata,
                "original_filename": filename,
                "file_type": processed_doc.file_type,
                "num_elements": processed_doc.num_elements,
                "processing_strategy": strategy,
                "routing_rule": routing.rule_name,
                "content_hash": content_hash
            }

            # 7. Index document to store
            doc_id = f"{routing.store_id}_{content_hash[:12]}"

            logger.info(f"Indexing {filename} to store {routing.store_id} as {doc_id}")

            index_request = IndexDocumentRequest(
                doc_id=doc_id,
                title=metadata.get('title', filename),
                content=content,
                author=metadata.get('author'),
                tags=metadata.get('tags', []),
                metadata=doc_metadata
            )

            await self.store_api.index_document(routing.store_id, index_request)

            # 8. Track processed file
            self.processed_hashes[content_hash] = doc_id

            processing_time = time.time() - start_time

            logger.info(f"Successfully ingested {filename} to {routing.store_id} in {processing_time:.2f}s")

            return IngestionResult(
                success=True,
                filename=filename,
                store_id=routing.store_id,
                doc_id=doc_id,
                num_chunks=0,  # Will be set by store
                routing_info={
                    "rule_id": routing.rule_id,
                    "rule_name": routing.rule_name,
                    "confidence": routing.confidence
                },
                processing_time_seconds=processing_time
            )

        except Exception as e:
            logger.error(f"Error ingesting {filename}: {str(e)}", exc_info=True)
            processing_time = time.time() - start_time

            return IngestionResult(
                success=False,
                filename=filename,
                store_id="",
                doc_id="",
                num_chunks=0,
                error=str(e),
                processing_time_seconds=processing_time
            )

    async def ingest_directory(
        self,
        directory: str,
        recursive: bool = True,
        file_pattern: str = "*",
        metadata: Optional[Dict[str, Any]] = None,
        strategy: str = "auto",
        max_concurrent: int = 5
    ) -> List[IngestionResult]:
        """
        Ingest all files in a directory.

        Args:
            directory: Path to directory
            recursive: Process subdirectories recursively
            file_pattern: Glob pattern for files (e.g., "*.pdf")
            metadata: Base metadata for all documents
            strategy: Unstructured processing strategy
            max_concurrent: Maximum concurrent ingestions

        Returns:
            List of IngestionResults
        """
        directory = Path(directory)

        if not directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")

        # Collect files
        if recursive:
            files = list(directory.rglob(file_pattern))
        else:
            files = list(directory.glob(file_pattern))

        files = [f for f in files if f.is_file()]

        logger.info(f"Found {len(files)} files to ingest from {directory}")

        # Process files with concurrency limit
        results = []
        semaphore = asyncio.Semaphore(max_concurrent)

        async def ingest_with_semaphore(filepath):
            async with semaphore:
                return await self.ingest_file(
                    filepath=str(filepath),
                    metadata=metadata,
                    strategy=strategy
                )

        tasks = [ingest_with_semaphore(f) for f in files]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error ingesting {files[i]}: {str(result)}")
                final_results.append(IngestionResult(
                    success=False,
                    filename=files[i].name,
                    store_id="",
                    doc_id="",
                    num_chunks=0,
                    error=str(result)
                ))
            else:
                final_results.append(result)

        return final_results

    async def _ensure_store_exists(self, store_id: str):
        """Ensure a knowledge store exists, creating it if necessary"""
        try:
            # Check if store exists
            existing_stores = await self.store_api.list_stores()
            store_ids = [s.store_id for s in existing_stores]

            if store_id in store_ids:
                return  # Store already exists

            # Get configuration for this store
            config = self.store_configs.get(store_id, {})

            logger.info(f"Auto-creating knowledge store: {store_id}")

            # Create store
            create_request = CreateStoreRequest(
                store_id=store_id,
                name=config.get('name', store_id.replace('_', ' ').title()),
                description=config.get('description', f'Auto-created store for {store_id}'),
                store_type=config.get('store_type', 'documents'),
                requires_roles=config.get('requires_roles', ['employee']),
                pii_level=config.get('pii_level', 'partial'),
                audit_level=config.get('audit_level', 'detailed'),
                connection_config={}
            )

            await self.store_api.create_store(create_request)
            logger.info(f"Successfully created store: {store_id}")

        except Exception as e:
            logger.error(f"Error ensuring store {store_id} exists: {str(e)}")
            raise

    def _compute_file_hash(self, filepath: Path) -> str:
        """Compute SHA256 hash of file content"""
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    async def get_ingestion_statistics(self) -> Dict[str, Any]:
        """Get ingestion statistics"""
        routing_stats = self.router.get_routing_statistics()

        return {
            "total_processed_files": len(self.processed_hashes),
            "routing_statistics": routing_stats,
            "unstructured_api_healthy": self.unstructured_client.health_check()
        }

    async def clear_history(self):
        """Clear ingestion history (for testing)"""
        self.processed_hashes.clear()
