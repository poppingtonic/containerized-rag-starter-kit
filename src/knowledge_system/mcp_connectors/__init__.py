"""
MCP Connectors for Knowledge Stores

Model Context Protocol connectors for different knowledge stores:
- Meeting transcripts
- Email messages
- SharePoint documents
- Custom sources
"""

from .base import MCPConnector
from .meetings import MeetingsConnector
from .emails import EmailsConnector
from .sharepoint import SharePointConnector

__all__ = [
    "MCPConnector",
    "MeetingsConnector",
    "EmailsConnector",
    "SharePointConnector",
]
