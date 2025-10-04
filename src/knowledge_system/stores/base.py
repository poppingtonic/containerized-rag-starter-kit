"""
Base Knowledge Store interface and types
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class StoreType(Enum):
    """Types of knowledge stores"""
    MEETINGS = "meetings"
    EMAILS = "emails"
    SHARED_DOCUMENTS = "shared_documents"
    CONFIDENTIAL = "confidential"
    PROJECT_TEAM = "project_team"
    CUSTOM = "custom"


@dataclass
class StoreMetadata:
    """Metadata about a knowledge store"""
    store_id: str
    store_type: StoreType
    name: str
    description: str
    enabled: bool
    requires_roles: List[str]
    pii_level: str  # "full", "partial", "metadata_only"
    audit_level: str  # "basic", "detailed", "forensic"
    created_at: datetime
    updated_at: datetime
    connection_config: Dict[str, Any]


@dataclass
class DocumentMetadata:
    """Metadata about a document in a store"""
    doc_id: str
    store_id: str
    title: str
    author: Optional[str]
    created_at: datetime
    updated_at: datetime
    tags: List[str]
    permissions: Dict[str, Any]
    sensitivity_level: str
    content_hash: str
    size_bytes: int
    custom_metadata: Dict[str, Any]


@dataclass
class QueryResult:
    """Result from a knowledge store query"""
    doc_id: str
    store_id: str
    content: str
    metadata: DocumentMetadata
    similarity_score: float
    chunks: List[Dict[str, Any]]
    entities: List[Dict[str, str]]
    obfuscated: bool


class KnowledgeStore(ABC):
    """
    Abstract base class for knowledge stores.

    Each store implementation must:
    1. Handle authentication to the backing service
    2. Implement document indexing and retrieval
    3. Support permission checking at document level
    4. Provide metadata extraction
    5. Enable audit logging
    """

    def __init__(self, metadata: StoreMetadata):
        self.metadata = metadata
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize connection to the knowledge store.

        Returns:
            bool: True if initialization succeeded
        """
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of the knowledge store connection.

        Returns:
            Dict with status, latency, and any issues
        """
        pass

    @abstractmethod
    async def index_document(
        self,
        doc_id: str,
        content: str,
        metadata: DocumentMetadata
    ) -> bool:
        """
        Index a document in the store.

        Args:
            doc_id: Unique document identifier
            content: Document content
            metadata: Document metadata

        Returns:
            bool: True if indexing succeeded
        """
        pass

    @abstractmethod
    async def query(
        self,
        query_text: str,
        user_id: str,
        user_roles: List[str],
        max_results: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[QueryResult]:
        """
        Query the knowledge store with permission checking.

        Args:
            query_text: Natural language query
            user_id: User making the query
            user_roles: Roles assigned to the user
            max_results: Maximum number of results to return
            filters: Additional filters (date range, tags, etc.)

        Returns:
            List of query results with permissions applied
        """
        pass

    @abstractmethod
    async def get_document(
        self,
        doc_id: str,
        user_id: str,
        user_roles: List[str]
    ) -> Optional[QueryResult]:
        """
        Retrieve a specific document by ID with permission check.

        Args:
            doc_id: Document identifier
            user_id: User requesting the document
            user_roles: Roles assigned to the user

        Returns:
            QueryResult if user has access, None otherwise
        """
        pass

    @abstractmethod
    async def check_permission(
        self,
        doc_id: str,
        user_id: str,
        user_roles: List[str],
        operation: str = "read"
    ) -> bool:
        """
        Check if user has permission for an operation on a document.

        Args:
            doc_id: Document identifier
            user_id: User to check
            user_roles: Roles assigned to the user
            operation: Operation type (read, write, delete)

        Returns:
            bool: True if user has permission
        """
        pass

    @abstractmethod
    async def list_documents(
        self,
        user_id: str,
        user_roles: List[str],
        limit: int = 100,
        offset: int = 0
    ) -> List[DocumentMetadata]:
        """
        List documents accessible to the user.

        Args:
            user_id: User requesting the list
            user_roles: Roles assigned to the user
            limit: Maximum number of documents to return
            offset: Pagination offset

        Returns:
            List of document metadata
        """
        pass

    @abstractmethod
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the knowledge store.

        Returns:
            Dict with document count, size, last updated, etc.
        """
        pass

    def is_initialized(self) -> bool:
        """Check if store is initialized"""
        return self._initialized

    def get_required_roles(self) -> List[str]:
        """Get roles required to access this store"""
        return self.metadata.requires_roles

    def get_pii_level(self) -> str:
        """Get PII protection level for this store"""
        return self.metadata.pii_level

    def get_audit_level(self) -> str:
        """Get audit logging level for this store"""
        return self.metadata.audit_level
