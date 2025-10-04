"""
SharePoint Knowledge Store Connector

MCP connector for SharePoint documents and sites.
Uses Microsoft Graph API via MCP.
"""

import logging
from typing import Any, Dict, List, Optional

from .base import MCPConnector

logger = logging.getLogger(__name__)


class SharePointConnector(MCPConnector):
    """
    Connector for SharePoint documents via Microsoft Graph API.

    Expected MCP tools:
    - search_sharepoint: Search across SharePoint sites
    - get_document: Get specific document
    - list_sites: List accessible sites
    - get_site_documents: Get documents from a site
    """

    def __init__(self, metadata, tenant_id: str, site_id: Optional[str] = None):
        """
        Initialize SharePoint connector.

        Args:
            metadata: Store metadata
            tenant_id: Microsoft tenant ID
            site_id: Optional specific site ID to query
        """
        # MCP server would be a Graph API MCP server
        super().__init__(
            metadata,
            mcp_server_command=["node", "/path/to/sharepoint-mcp-server"],
            mcp_server_args=[f"--tenant={tenant_id}"]
        )
        self.tenant_id = tenant_id
        self.site_id = site_id

    async def _mcp_query(
        self,
        query_text: str,
        max_results: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Query SharePoint via MCP"""
        if not self.session:
            raise RuntimeError("MCP session not initialized")

        try:
            args = {
                "query": query_text,
                "max_results": max_results
            }

            # Add site filter if configured
            if self.site_id:
                args["site_id"] = self.site_id

            # Add additional filters
            if filters:
                if "site" in filters:
                    args["site_id"] = filters["site"]
                if "library" in filters:
                    args["library"] = filters["library"]
                if "file_type" in filters:
                    args["file_type"] = filters["file_type"]
                if "modified_by" in filters:
                    args["modified_by"] = filters["modified_by"]

            result = await self.session.call_tool("search_sharepoint", args)

            if result and result.content:
                import json
                data = json.loads(result.content[0].text)
                return data.get("documents", [])

            return []

        except Exception as e:
            logger.error(f"Error querying SharePoint via MCP: {str(e)}")
            return []

    async def _mcp_get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a SharePoint document by ID via MCP"""
        if not self.session:
            raise RuntimeError("MCP session not initialized")

        try:
            result = await self.session.call_tool(
                "get_document",
                {"document_id": doc_id}
            )

            if result and result.content:
                import json
                data = json.loads(result.content[0].text)
                return data.get("document")

            return None

        except Exception as e:
            logger.error(f"Error getting SharePoint document via MCP: {str(e)}")
            return None

    async def check_permission(
        self,
        doc_id: str,
        user_id: str,
        user_roles: List[str],
        operation: str = "read"
    ) -> bool:
        """
        Check if user can access a SharePoint document.

        Uses SharePoint/Graph API permissions.
        """
        document = await self._mcp_get_document(doc_id)
        if not document:
            return False

        # Check SharePoint permissions
        permissions = document.get("permissions", {})

        # Check if user has direct permission
        allowed_users = permissions.get("allowed_users", [])
        if user_id in allowed_users:
            return True

        # Check if user's role has permission
        allowed_roles = permissions.get("allowed_roles", [])
        if any(role in allowed_roles for role in user_roles):
            return True

        # Check SharePoint groups
        user_groups = permissions.get("user_groups", {}).get(user_id, [])
        allowed_groups = permissions.get("allowed_groups", [])
        if any(group in allowed_groups for group in user_groups):
            return True

        return False

    async def list_sites(self, user_id: str) -> List[Dict[str, Any]]:
        """List SharePoint sites accessible to user"""
        if not self.session:
            raise RuntimeError("MCP session not initialized")

        try:
            result = await self.session.call_tool(
                "list_sites",
                {"user_id": user_id}
            )

            if result and result.content:
                import json
                data = json.loads(result.content[0].text)
                return data.get("sites", [])

            return []

        except Exception as e:
            logger.error(f"Error listing SharePoint sites: {str(e)}")
            return []
