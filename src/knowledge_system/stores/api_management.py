"""
Knowledge Store Management API

Provides REST API endpoints for dynamically adding, removing,
and managing knowledge stores.
"""

import logging
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from .base import StoreType, StoreMetadata
from .manager import KnowledgeStoreManager
from .database_store import DatabaseBackedStore

logger = logging.getLogger(__name__)


# Request/Response Models

class CreateStoreRequest(BaseModel):
    """Request to create a new knowledge store"""
    store_id: str
    name: str
    description: str
    store_type: str  # "meetings", "emails", etc.
    requires_roles: List[str] = []
    pii_level: str = "partial"
    audit_level: str = "detailed"
    connection_config: dict = {}


class StoreResponse(BaseModel):
    """Response with store information"""
    store_id: str
    name: str
    description: str
    store_type: str
    enabled: bool
    requires_roles: List[str]
    pii_level: str
    audit_level: str
    created_at: str
    statistics: dict = {}


class StoreHealthResponse(BaseModel):
    """Health status of a store"""
    store_id: str
    healthy: bool
    error: Optional[str] = None


class IndexDocumentRequest(BaseModel):
    """Request to index a document into a store"""
    doc_id: str
    title: str
    content: str
    author: Optional[str] = None
    tags: List[str] = []
    metadata: dict = {}


# API Functions

class StoreManagementAPI:
    """
    API for managing knowledge stores.

    Provides CRUD operations for stores and document indexing.
    """

    def __init__(
        self,
        store_manager: KnowledgeStoreManager,
        db_connection_string: str,
        openai_api_key: str
    ):
        self.store_manager = store_manager
        self.db_connection_string = db_connection_string
        self.openai_api_key = openai_api_key

    async def create_store(self, request: CreateStoreRequest) -> StoreResponse:
        """
        Create a new knowledge store.

        The store will share the existing PostgreSQL database
        but partition data by store_id.
        """
        # Validate store_type
        try:
            store_type = StoreType(request.store_type)
        except ValueError:
            store_type = StoreType.CUSTOM

        # Create store metadata
        metadata = StoreMetadata(
            store_id=request.store_id,
            store_type=store_type,
            name=request.name,
            description=request.description,
            enabled=True,
            requires_roles=request.requires_roles,
            pii_level=request.pii_level,
            audit_level=request.audit_level,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            connection_config=request.connection_config
        )

        # Create database-backed store
        store = DatabaseBackedStore(
            metadata=metadata,
            db_connection_string=self.db_connection_string,
            openai_api_key=self.openai_api_key
        )

        # Initialize store
        success = await store.initialize()
        if not success:
            raise RuntimeError(f"Failed to initialize store {request.store_id}")

        # Register with manager
        self.store_manager.register_store(store)

        # Get statistics
        stats = await store.get_statistics()

        logger.info(f"Created knowledge store: {request.store_id}")

        return StoreResponse(
            store_id=metadata.store_id,
            name=metadata.name,
            description=metadata.description,
            store_type=metadata.store_type.value,
            enabled=metadata.enabled,
            requires_roles=metadata.requires_roles,
            pii_level=metadata.pii_level,
            audit_level=metadata.audit_level,
            created_at=metadata.created_at.isoformat(),
            statistics=stats
        )

    async def list_stores(self) -> List[StoreResponse]:
        """List all registered knowledge stores"""
        stores = self.store_manager.list_stores()

        responses = []
        for metadata in stores:
            store = self.store_manager.get_store(metadata.store_id)
            if store:
                stats = await store.get_statistics()
            else:
                stats = {}

            responses.append(StoreResponse(
                store_id=metadata.store_id,
                name=metadata.name,
                description=metadata.description,
                store_type=metadata.store_type.value,
                enabled=metadata.enabled,
                requires_roles=metadata.requires_roles,
                pii_level=metadata.pii_level,
                audit_level=metadata.audit_level,
                created_at=metadata.created_at.isoformat(),
                statistics=stats
            ))

        return responses

    async def get_store(self, store_id: str) -> Optional[StoreResponse]:
        """Get information about a specific store"""
        store = self.store_manager.get_store(store_id)
        if not store:
            return None

        stats = await store.get_statistics()
        metadata = store.metadata

        return StoreResponse(
            store_id=metadata.store_id,
            name=metadata.name,
            description=metadata.description,
            store_type=metadata.store_type.value,
            enabled=metadata.enabled,
            requires_roles=metadata.requires_roles,
            pii_level=metadata.pii_level,
            audit_level=metadata.audit_level,
            created_at=metadata.created_at.isoformat(),
            statistics=stats
        )

    async def delete_store(self, store_id: str) -> bool:
        """
        Remove a knowledge store from the manager.

        Note: This does NOT delete the data from the database.
        Data remains partitioned by store_id and can be re-registered.
        """
        success = self.store_manager.unregister_store(store_id)
        if success:
            logger.info(f"Deleted knowledge store: {store_id}")
        return success

    async def check_store_health(self, store_id: str) -> StoreHealthResponse:
        """Check health of a knowledge store"""
        store = self.store_manager.get_store(store_id)
        if not store:
            return StoreHealthResponse(
                store_id=store_id,
                healthy=False,
                error="Store not found"
            )

        health = await store.health_check()

        return StoreHealthResponse(
            store_id=store_id,
            healthy=health.get("healthy", False),
            error=health.get("error")
        )

    async def index_document(
        self,
        store_id: str,
        request: IndexDocumentRequest
    ) -> dict:
        """
        Index a document into a specific knowledge store.

        The document will be:
        1. Chunked into smaller pieces
        2. Embedded using OpenAI
        3. Stored in the shared database with store_id partition
        4. Indexed for vector similarity search
        """
        store = self.store_manager.get_store(store_id)
        if not store:
            raise ValueError(f"Store {store_id} not found")

        # Create document metadata
        from .base import DocumentMetadata
        doc_metadata = DocumentMetadata(
            doc_id=request.doc_id,
            store_id=store_id,
            title=request.title,
            author=request.author,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            tags=request.tags,
            permissions={},
            sensitivity_level=store.metadata.pii_level,
            content_hash="",
            size_bytes=len(request.content),
            custom_metadata=request.metadata
        )

        # Index the document
        success = await store.index_document(
            doc_id=request.doc_id,
            content=request.content,
            metadata=doc_metadata
        )

        if not success:
            raise RuntimeError(f"Failed to index document {request.doc_id}")

        logger.info(f"Indexed document {request.doc_id} in store {store_id}")

        return {
            "success": True,
            "doc_id": request.doc_id,
            "store_id": store_id,
            "message": "Document indexed successfully"
        }

    async def get_store_statistics(self, store_id: str) -> dict:
        """Get detailed statistics for a store"""
        store = self.store_manager.get_store(store_id)
        if not store:
            raise ValueError(f"Store {store_id} not found")

        return await store.get_statistics()
