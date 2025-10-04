"""
Knowledge Store Abstraction Layer

Provides unified interface for multiple knowledge stores:
- Meeting transcripts
- Email messages
- Shared documents
- Confidential data
- Project team stores
"""

from .base import KnowledgeStore, StoreMetadata, StoreType
from .manager import KnowledgeStoreManager

__all__ = [
    "KnowledgeStore",
    "StoreMetadata",
    "StoreType",
    "KnowledgeStoreManager",
]
