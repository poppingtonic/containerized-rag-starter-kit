"""
Azure Bot Framework Adapter

For integration with Microsoft Teams and other Bot Framework channels.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request, HTTPException

logger = logging.getLogger(__name__)


class BotFrameworkAdapter:
    """
    Azure Bot Framework adapter for Microsoft Teams integration.

    Handles Bot Framework protocol and Teams-specific features.
    """

    def __init__(
        self,
        app_id: str,
        app_password: str,
        workflow_router: Any
    ):
        self.app_id = app_id
        self.app_password = app_password
        self.workflow_router = workflow_router
        self.router = APIRouter(prefix="/bot-framework", tags=["bot-framework"])

        self._register_routes()

    def _register_routes(self):
        """Register Bot Framework endpoints"""

        @self.router.post("/messages")
        async def handle_activity(request: Request):
            """
            Handle Bot Framework activity (messages, events, etc.)

            This endpoint receives activities from Bot Framework channels
            like Microsoft Teams, Slack, etc.
            """
            try:
                activity = await request.json()

                # Verify the request (Bot Framework authentication)
                # In production, would verify JWT token from Bot Framework
                # await self._verify_bot_framework_request(request)

                activity_type = activity.get("type")

                if activity_type == "message":
                    return await self._handle_message(activity)
                elif activity_type == "conversationUpdate":
                    return await self._handle_conversation_update(activity)
                elif activity_type == "invoke":
                    return await self._handle_invoke(activity)
                else:
                    logger.warning(f"Unhandled activity type: {activity_type}")
                    return {"status": "ok"}

            except Exception as e:
                logger.error(f"Error handling Bot Framework activity: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/health")
        async def health_check():
            """Health check for Bot Framework integration"""
            return {
                "status": "healthy",
                "service": "knowledge-system-bot-framework"
            }

    async def _handle_message(self, activity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle message activity.

        Args:
            activity: Bot Framework activity object

        Returns:
            Response activity
        """
        text = activity.get("text", "")
        user_id = activity.get("from", {}).get("id")
        conversation_id = activity.get("conversation", {}).get("id")

        # Simple echo response (would integrate with workflow router)
        response_text = f"You said: {text}"

        # Build response activity
        response = {
            "type": "message",
            "text": response_text,
            "conversation": activity.get("conversation"),
            "recipient": activity.get("from"),
            "from": activity.get("recipient")
        }

        return response

    async def _handle_conversation_update(self, activity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle conversation update (bot added to conversation, etc.)

        Args:
            activity: Bot Framework activity object

        Returns:
            Response activity
        """
        members_added = activity.get("membersAdded", [])

        # Check if bot was added
        for member in members_added:
            if member.get("id") == activity.get("recipient", {}).get("id"):
                # Bot was added to conversation - send welcome message
                welcome_text = (
                    "Hello! I'm your knowledge assistant. "
                    "I can help you search meetings, emails, and documents. "
                    "Just ask me a question!"
                )

                return {
                    "type": "message",
                    "text": welcome_text,
                    "conversation": activity.get("conversation"),
                    "recipient": activity.get("from"),
                    "from": activity.get("recipient")
                }

        return {"status": "ok"}

    async def _handle_invoke(self, activity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle invoke activity (Adaptive Card actions, etc.)

        Args:
            activity: Bot Framework activity object

        Returns:
            Invoke response
        """
        invoke_name = activity.get("name")

        if invoke_name == "adaptiveCard/action":
            # Handle Adaptive Card action
            data = activity.get("value", {})
            action = data.get("action")

            # Process action
            logger.info(f"Adaptive Card action: {action}")

        return {
            "type": "invokeResponse",
            "value": {
                "status": 200,
                "body": {"message": "Action processed"}
            }
        }

    async def _verify_bot_framework_request(self, request: Request) -> bool:
        """
        Verify Bot Framework request authentication.

        In production, this would:
        1. Extract JWT token from Authorization header
        2. Verify token signature using Bot Framework public keys
        3. Validate claims (app_id, service_url, etc.)

        Args:
            request: FastAPI request object

        Returns:
            bool: True if request is valid

        Raises:
            HTTPException: If authentication fails
        """
        # Simplified - production would use botbuilder-python library
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization")

        # Would verify JWT token here
        # token = auth_header[7:]
        # verify_jwt(token, self.app_id)

        return True

    def get_router(self) -> APIRouter:
        """Get FastAPI router for integration"""
        return self.router
