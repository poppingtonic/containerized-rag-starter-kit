"""
Base MCP Connector

Abstract base for MCP-based knowledge store connectors.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ..stores.base import KnowledgeStore, QueryResult, DocumentMetadata

logger = logging.getLogger(__name__)


class MCPConnector(KnowledgeStore, ABC):
    """
    Base class for MCP-based knowledge store connectors.

    Extends KnowledgeStore to use Model Context Protocol for
    communication with external knowledge sources.
    """

    def __init__(self, metadata, mcp_server_command: List[str], mcp_server_args: List[str] = []):
        super().__init__(metadata)
        self.mcp_server_command = mcp_server_command
        self.mcp_server_args = mcp_server_args
        self.session: Optional[ClientSession] = None
        self._server_params: Optional[StdioServerParameters] = None

    async def initialize(self) -> bool:
        """Initialize MCP connection"""
        try:
            # Create server parameters
            self._server_params = StdioServerParameters(
                command=self.mcp_server_command[0],
                args=self.mcp_server_command[1:] + self.mcp_server_args,
                env=None
            )

            # Initialize MCP session
            stdio_transport = await stdio_client(self._server_params)
            self.session = ClientSession(stdio_transport.read, stdio_transport.write)

            await self.session.initialize()

            self._initialized = True
            logger.info(f"Initialized MCP connector for {self.metadata.store_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize MCP connector: {str(e)}")
            self._initialized = False
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Check MCP connection health"""
        if not self._initialized or not self.session:
            return {
                "healthy": False,
                "error": "Not initialized"
            }

        try:
            # Try to list tools as a health check
            tools = await self.session.list_tools()
            return {
                "healthy": True,
                "tools_available": len(tools.tools),
                "store_id": self.metadata.store_id
            }
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "healthy": False,
                "error": str(e)
            }

    @abstractmethod
    async def _mcp_query(
        self,
        query_text: str,
        max_results: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute MCP query to the backing service.

        Args:
            query_text: Query string
            max_results: Maximum results to return
            filters: Additional filters

        Returns:
            List of result dictionaries from MCP tool
        """
        pass

    @abstractmethod
    async def _mcp_get_document(
        self,
        doc_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a document via MCP.

        Args:
            doc_id: Document identifier

        Returns:
            Document data or None
        """
        pass

    async def query(
        self,
        query_text: str,
        user_id: str,
        user_roles: List[str],
        max_results: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[QueryResult]:
        """
        Query the knowledge store via MCP.

        Implements permission checking and result filtering.
        """
        if not self._initialized:
            raise RuntimeError("MCP connector not initialized")

        # Execute MCP query
        raw_results = await self._mcp_query(query_text, max_results, filters)

        # Convert to QueryResult objects with permission checking
        results = []
        for raw in raw_results:
            # Check document-level permission
            doc_id = raw.get("doc_id")
            if doc_id:
                has_permission = await self.check_permission(
                    doc_id,
                    user_id,
                    user_roles,
                    "read"
                )
                if not has_permission:
                    continue

            # Convert to QueryResult
            result = self._convert_to_query_result(raw)
            results.append(result)

        return results

    async def get_document(
        self,
        doc_id: str,
        user_id: str,
        user_roles: List[str]
    ) -> Optional[QueryResult]:
        """Get a document by ID via MCP"""
        if not self._initialized:
            raise RuntimeError("MCP connector not initialized")

        # Check permission first
        has_permission = await self.check_permission(
            doc_id,
            user_id,
            user_roles,
            "read"
        )

        if not has_permission:
            return None

        # Get document via MCP
        raw = await self._mcp_get_document(doc_id)
        if not raw:
            return None

        return self._convert_to_query_result(raw)

    def _convert_to_query_result(self, raw: Dict[str, Any]) -> QueryResult:
        """
        Convert raw MCP result to QueryResult.

        Args:
            raw: Raw result from MCP tool

        Returns:
            QueryResult object
        """
        # Extract metadata
        metadata = DocumentMetadata(
            doc_id=raw.get("doc_id", ""),
            store_id=self.metadata.store_id,
            title=raw.get("title", ""),
            author=raw.get("author"),
            created_at=raw.get("created_at"),
            updated_at=raw.get("updated_at"),
            tags=raw.get("tags", []),
            permissions=raw.get("permissions", {}),
            sensitivity_level=raw.get("sensitivity_level", "internal"),
            content_hash=raw.get("content_hash", ""),
            size_bytes=raw.get("size_bytes", 0),
            custom_metadata=raw.get("metadata", {})
        )

        return QueryResult(
            doc_id=raw.get("doc_id", ""),
            store_id=self.metadata.store_id,
            content=raw.get("content", ""),
            metadata=metadata,
            similarity_score=raw.get("similarity_score", 0.0),
            chunks=raw.get("chunks", []),
            entities=raw.get("entities", []),
            obfuscated=False
        )

    async def index_document(
        self,
        doc_id: str,
        content: str,
        metadata: DocumentMetadata
    ) -> bool:
        """
        Index a document via MCP.

        Override in subclass if MCP tool supports indexing.
        """
        logger.warning(f"Indexing not supported for {self.metadata.store_id}")
        return False

    async def check_permission(
        self,
        doc_id: str,
        user_id: str,
        user_roles: List[str],
        operation: str = "read"
    ) -> bool:
        """
        Check permission for a document.

        Override in subclass for custom permission logic.
        """
        # Default: check against required roles
        required_roles = self.metadata.requires_roles
        if not required_roles:
            return True

        return any(role in user_roles for role in required_roles)

    async def list_documents(
        self,
        user_id: str,
        user_roles: List[str],
        limit: int = 100,
        offset: int = 0
    ) -> List[DocumentMetadata]:
        """
        List documents via MCP.

        Override in subclass if MCP tool supports listing.
        """
        logger.warning(f"Document listing not supported for {self.metadata.store_id}")
        return []

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics via MCP.

        Override in subclass if MCP tool provides statistics.
        """
        return {
            "store_id": self.metadata.store_id,
            "type": self.metadata.store_type.value,
            "initialized": self._initialized,
            "message": "Statistics not available"
        }

    async def shutdown(self) -> None:
        """Shutdown MCP connection"""
        if self.session:
            # MCP session cleanup if needed
            self.session = None
        self._initialized = False
        logger.info(f"Shut down MCP connector for {self.metadata.store_id}")
