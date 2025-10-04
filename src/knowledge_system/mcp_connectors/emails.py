"""
Emails Knowledge Store Connector

MCP connector for email messages and threads.
"""

import logging
from typing import Any, Dict, List, Optional

from .base import MCPConnector

logger = logging.getLogger(__name__)


class EmailsConnector(MCPConnector):
    """
    Connector for email messages knowledge store.

    Expected MCP tools:
    - search_emails: Search email messages
    - get_email: Get specific email by ID
    - get_thread: Get email thread
    """

    async def _mcp_query(
        self,
        query_text: str,
        max_results: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Query emails via MCP"""
        if not self.session:
            raise RuntimeError("MCP session not initialized")

        try:
            args = {
                "query": query_text,
                "max_results": max_results
            }

            # Add filters
            if filters:
                if "date_range" in filters:
                    args["date_range"] = filters["date_range"]
                if "sender" in filters:
                    args["sender"] = filters["sender"]
                if "folder" in filters:
                    args["folder"] = filters["folder"]
                if "has_attachments" in filters:
                    args["has_attachments"] = filters["has_attachments"]

            result = await self.session.call_tool("search_emails", args)

            if result and result.content:
                import json
                data = json.loads(result.content[0].text)
                return data.get("emails", [])

            return []

        except Exception as e:
            logger.error(f"Error querying emails via MCP: {str(e)}")
            return []

    async def _mcp_get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get an email by ID via MCP"""
        if not self.session:
            raise RuntimeError("MCP session not initialized")

        try:
            result = await self.session.call_tool("get_email", {"email_id": doc_id})

            if result and result.content:
                import json
                data = json.loads(result.content[0].text)
                return data.get("email")

            return None

        except Exception as e:
            logger.error(f"Error getting email via MCP: {str(e)}")
            return None

    async def check_permission(
        self,
        doc_id: str,
        user_id: str,
        user_roles: List[str],
        operation: str = "read"
    ) -> bool:
        """
        Check if user can access an email.

        Permission logic:
        - User can access their own emails (sent or received)
        - Managers can access team emails (if delegated)
        - Admins can access all emails
        """
        email = await self._mcp_get_document(doc_id)
        if not email:
            return False

        # Check if user is sender or recipient
        sender = email.get("sender")
        recipients = email.get("recipients", [])
        cc = email.get("cc", [])

        if user_id == sender or user_id in recipients or user_id in cc:
            return True

        # Check role-based access
        if "admin" in user_roles:
            return True

        # Check if user has delegated access
        delegated_to = email.get("delegated_access", [])
        if user_id in delegated_to:
            return True

        return False
