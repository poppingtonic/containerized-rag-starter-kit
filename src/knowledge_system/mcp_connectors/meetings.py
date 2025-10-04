"""
Meetings Knowledge Store Connector

MCP connector for meeting transcripts and notes.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import MCPConnector

logger = logging.getLogger(__name__)


class MeetingsConnector(MCPConnector):
    """
    Connector for meeting transcripts knowledge store.

    Expected MCP tools:
    - search_meetings: Search meeting transcripts
    - get_meeting: Get specific meeting by ID
    - list_meetings: List recent meetings
    """

    async def _mcp_query(
        self,
        query_text: str,
        max_results: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Query meetings via MCP"""
        if not self.session:
            raise RuntimeError("MCP session not initialized")

        try:
            # Build MCP tool arguments
            args = {
                "query": query_text,
                "max_results": max_results
            }

            # Add filters if provided
            if filters:
                if "date_range" in filters:
                    args["date_range"] = filters["date_range"]
                if "participants" in filters:
                    args["participants"] = filters["participants"]
                if "tags" in filters:
                    args["tags"] = filters["tags"]

            # Call MCP tool
            result = await self.session.call_tool("search_meetings", args)

            # Parse result
            if result and result.content:
                import json
                data = json.loads(result.content[0].text)
                return data.get("meetings", [])

            return []

        except Exception as e:
            logger.error(f"Error querying meetings via MCP: {str(e)}")
            return []

    async def _mcp_get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a meeting by ID via MCP"""
        if not self.session:
            raise RuntimeError("MCP session not initialized")

        try:
            result = await self.session.call_tool("get_meeting", {"meeting_id": doc_id})

            if result and result.content:
                import json
                data = json.loads(result.content[0].text)
                return data.get("meeting")

            return None

        except Exception as e:
            logger.error(f"Error getting meeting via MCP: {str(e)}")
            return None

    async def list_documents(
        self,
        user_id: str,
        user_roles: List[str],
        limit: int = 100,
        offset: int = 0
    ) -> List:
        """List recent meetings"""
        if not self.session:
            raise RuntimeError("MCP session not initialized")

        try:
            result = await self.session.call_tool(
                "list_meetings",
                {"limit": limit, "offset": offset}
            )

            if result and result.content:
                import json
                data = json.loads(result.content[0].text)
                meetings = data.get("meetings", [])

                # Convert to DocumentMetadata objects
                # (simplified - would create proper metadata)
                return meetings

            return []

        except Exception as e:
            logger.error(f"Error listing meetings: {str(e)}")
            return []

    async def check_permission(
        self,
        doc_id: str,
        user_id: str,
        user_roles: List[str],
        operation: str = "read"
    ) -> bool:
        """
        Check if user can access a meeting.

        Permission logic:
        - Participants can always access
        - Managers can access all team meetings
        - Others need explicit permission
        """
        # Get meeting details
        meeting = await self._mcp_get_document(doc_id)
        if not meeting:
            return False

        # Check if user was a participant
        participants = meeting.get("participants", [])
        if user_id in participants:
            return True

        # Check role-based access
        if "manager" in user_roles or "admin" in user_roles:
            return True

        # Check explicit permissions
        allowed_users = meeting.get("permissions", {}).get("allowed_users", [])
        if user_id in allowed_users:
            return True

        return False
