"""
Ingestion Module

Provides intelligent document ingestion with:
- Multi-format document processing via unstructured-api
- Automatic routing to appropriate knowledge stores
- Deduplication
- Metadata extraction
"""

from .unstructured_client import (
    UnstructuredClient,
    ProcessedDocument,
    ProcessedElement
)
from .document_router import (
    DocumentRouter,
    RoutingRule,
    RoutingResult,
    RoutingStrategy
)
from .smart_ingestion_service import (
    SmartIngestionService,
    IngestionResult
)

__all__ = [
    "UnstructuredClient",
    "ProcessedDocument",
    "ProcessedElement",
    "DocumentRouter",
    "RoutingRule",
    "RoutingResult",
    "RoutingStrategy",
    "SmartIngestionService",
    "IngestionResult",
]
