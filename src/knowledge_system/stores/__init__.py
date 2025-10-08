"""
Knowledge Store Abstraction Layer

Provides unified interface for multiple knowledge stores:
- Meeting transcripts
- Email messages
- Shared documents
- Confidential data
- Project team stores

Includes dynamic store creation via DatabaseBackedStore and StoreManagementAPI.
"""

from .base import KnowledgeStore, StoreMetadata, StoreType
from .manager import KnowledgeStoreManager
from .database_store import DatabaseBackedStore
from .api_management import (
    StoreManagementAPI,
    CreateStoreRequest,
    StoreResponse,
    IndexDocumentRequest,
    StoreHealthResponse
)

__all__ = [
    "KnowledgeStore",
    "StoreMetadata",
    "StoreType",
    "KnowledgeStoreManager",
    "DatabaseBackedStore",
    "StoreManagementAPI",
    "CreateStoreRequest",
    "StoreResponse",
    "IndexDocumentRequest",
    "StoreHealthResponse",
]
