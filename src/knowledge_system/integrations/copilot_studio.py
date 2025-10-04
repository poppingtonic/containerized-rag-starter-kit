"""
Copilot Studio Integration

Adapter for Microsoft Copilot Studio with conversational flow support.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from ..workflows.router import WorkflowRouter
from ..workflows.models import WorkflowContext

logger = logging.getLogger(__name__)


class CopilotMessage(BaseModel):
    """Message model for Copilot Studio"""
    text: str
    user_id: str
    conversation_id: str
    workflow_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class CopilotResponse(BaseModel):
    """Response model for Copilot Studio"""
    text: str
    suggestions: Optional[List[str]] = None
    cards: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None


class CopilotStudioAdapter:
    """
    Microsoft Copilot Studio adapter.

    Features:
    - Conversational flow integration
    - Rich card responses
    - Suggested actions
    - SSO with Microsoft 365
    """

    def __init__(
        self,
        workflow_router: WorkflowRouter,
        api_key: Optional[str] = None,
        enable_sso: bool = True
    ):
        self.workflow_router = workflow_router
        self.api_key = api_key
        self.enable_sso = enable_sso
        self.router = APIRouter(prefix="/copilot-studio", tags=["copilot-studio"])

        # Conversation state storage (in production, use Redis/DB)
        self.conversations: Dict[str, List[Dict]] = {}

        self._register_routes()

    def _register_routes(self):
        """Register Copilot Studio API routes"""

        @self.router.post("/message", response_model=CopilotResponse)
        async def handle_message(
            message: CopilotMessage,
            authorization: Optional[str] = Header(None)
        ):
            """
            Handle a message from Copilot Studio.

            Supports multi-turn conversations with context.
            """
            # Verify API key
            if self.api_key:
                if not authorization or authorization != f"Bearer {self.api_key}":
                    raise HTTPException(status_code=401, detail="Invalid API key")

            try:
                # Get or create conversation context
                conversation_history = self.conversations.get(message.conversation_id, [])

                # Determine workflow
                workflow_id = message.workflow_id or self._detect_workflow(
                    message.text,
                    conversation_history
                )

                if not workflow_id:
                    return CopilotResponse(
                        text="I'm not sure how to help with that. Which knowledge area would you like to search?",
                        suggestions=self._get_workflow_suggestions()
                    )

                # Create workflow context
                context = WorkflowContext(
                    workflow_id=workflow_id,
                    user_id=message.user_id,
                    user_email=message.user_id,  # Would get from SSO
                    user_roles=["copilot_user"],  # Would fetch from identity provider
                    metadata={
                        "source": "copilot_studio",
                        "conversation_id": message.conversation_id,
                        **(message.context or {})
                    }
                )

                # Execute query
                result = await self.workflow_router.execute_workflow(
                    workflow_id=workflow_id,
                    query=message.text,
                    context=context
                )

                # Store conversation turn
                conversation_history.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "user": message.text,
                    "assistant": result.answer,
                    "workflow": workflow_id
                })
                self.conversations[message.conversation_id] = conversation_history[-10:]  # Keep last 10 turns

                # Format response with cards if results available
                cards = None
                if result.results:
                    cards = self._format_result_cards(result.results[:3])

                # Generate follow-up suggestions
                suggestions = self._generate_suggestions(result, workflow_id)

                return CopilotResponse(
                    text=result.answer,
                    suggestions=suggestions,
                    cards=cards,
                    metadata={
                        "workflow": workflow_id,
                        "results_count": result.total_results,
                        "execution_time_ms": result.execution_time_ms
                    }
                )

            except Exception as e:
                logger.error(f"Error handling Copilot message: {str(e)}")
                return CopilotResponse(
                    text=f"I encountered an error: {str(e)}. Please try again.",
                    suggestions=["Try again", "Ask something else"]
                )

        @self.router.post("/conversation/reset")
        async def reset_conversation(
            conversation_id: str,
            authorization: Optional[str] = Header(None)
        ):
            """Reset conversation state"""
            if self.api_key:
                if not authorization or authorization != f"Bearer {self.api_key}":
                    raise HTTPException(status_code=401, detail="Invalid API key")

            if conversation_id in self.conversations:
                del self.conversations[conversation_id]

            return {"status": "reset", "conversation_id": conversation_id}

        @self.router.get("/health")
        async def health_check():
            """Health check for Copilot Studio integration"""
            return {
                "status": "healthy",
                "service": "knowledge-system-copilot-studio",
                "active_conversations": len(self.conversations)
            }

    def _detect_workflow(
        self,
        query: str,
        conversation_history: List[Dict]
    ) -> Optional[str]:
        """
        Detect appropriate workflow from query and conversation.

        Uses keyword matching and conversation context.
        """
        query_lower = query.lower()

        # Keyword-based detection
        if any(kw in query_lower for kw in ["meeting", "standup", "action items"]):
            return "meeting_tracker"
        elif any(kw in query_lower for kw in ["email", "message", "inbox"]):
            return "email_search"
        elif any(kw in query_lower for kw in ["project", "sprint", "task"]):
            return "project_assistant"
        elif any(kw in query_lower for kw in ["confidential", "market data", "research"]):
            return "confidential_research"

        # Use previous workflow if continuing conversation
        if conversation_history:
            last_turn = conversation_history[-1]
            return last_turn.get("workflow")

        return None

    def _get_workflow_suggestions(self) -> List[str]:
        """Get workflow selection suggestions"""
        workflows = self.workflow_router.list_workflows()
        return [wf.name for wf in workflows[:5] if wf.active]

    def _format_result_cards(self, results: List[Dict]) -> List[Dict[str, Any]]:
        """
        Format results as Adaptive Cards for Copilot.

        Uses Microsoft Adaptive Card format.
        """
        cards = []
        for result in results:
            metadata = result.get("metadata", {})
            card = {
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": [
                    {
                        "type": "TextBlock",
                        "text": metadata.get("title", "Document"),
                        "weight": "bolder",
                        "size": "medium"
                    },
                    {
                        "type": "TextBlock",
                        "text": result.get("content", "")[:200] + "...",
                        "wrap": True
                    },
                    {
                        "type": "FactSet",
                        "facts": [
                            {
                                "title": "Author",
                                "value": metadata.get("author", "Unknown")
                            },
                            {
                                "title": "Score",
                                "value": f"{result.get('similarity_score', 0):.2f}"
                            }
                        ]
                    }
                ]
            }
            cards.append(card)

        return cards

    def _generate_suggestions(
        self,
        result: Any,
        workflow_id: str
    ) -> List[str]:
        """Generate contextual follow-up suggestions"""
        suggestions = ["Tell me more", "Show different results"]

        # Add workflow-specific suggestions
        if workflow_id == "meeting_tracker":
            suggestions.append("Show action items")
        elif workflow_id == "project_assistant":
            suggestions.append("Show project status")

        return suggestions

    def get_router(self) -> APIRouter:
        """Get FastAPI router for integration"""
        return self.router
