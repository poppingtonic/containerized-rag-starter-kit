"""
Power Automate Integration

REST API adapter for Power Automate flows.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..workflows.router import WorkflowRouter
from ..workflows.models import WorkflowContext

logger = logging.getLogger(__name__)


class PowerAutomateQueryRequest(BaseModel):
    """Request model for Power Automate queries"""
    query: str
    workflow_id: str
    user_email: str
    max_results: Optional[int] = 50
    filters: Optional[Dict[str, Any]] = None


class PowerAutomateQueryResponse(BaseModel):
    """Response model for Power Automate queries"""
    success: bool
    query: str
    answer: str
    results: List[Dict[str, Any]]
    execution_time_ms: float
    error: Optional[str] = None


class PowerAutomateAdapter:
    """
    Power Automate REST API adapter.

    Provides HTTP endpoints compatible with Power Automate custom connectors.
    """

    def __init__(
        self,
        workflow_router: WorkflowRouter,
        api_key: Optional[str] = None
    ):
        self.workflow_router = workflow_router
        self.api_key = api_key
        self.router = APIRouter(prefix="/power-automate", tags=["power-automate"])

        # Register routes
        self._register_routes()

    def _register_routes(self):
        """Register API routes"""

        @self.router.post("/query", response_model=PowerAutomateQueryResponse)
        async def query(
            request: PowerAutomateQueryRequest,
            authorization: Optional[str] = Header(None)
        ):
            """
            Execute a workflow query from Power Automate.

            Requires API key authentication via Authorization header.
            """
            # Verify API key
            if self.api_key:
                if not authorization or authorization != f"Bearer {self.api_key}":
                    raise HTTPException(status_code=401, detail="Invalid API key")

            try:
                # Create workflow context
                context = WorkflowContext(
                    workflow_id=request.workflow_id,
                    user_id=request.user_email,
                    user_email=request.user_email,
                    user_roles=["power_automate_user"],  # Would fetch from identity provider
                    metadata={"source": "power_automate"}
                )

                # Execute workflow
                result = await self.workflow_router.execute_workflow(
                    workflow_id=request.workflow_id,
                    query=request.query,
                    context=context
                )

                return PowerAutomateQueryResponse(
                    success=True,
                    query=request.query,
                    answer=result.answer,
                    results=result.results[:request.max_results or 50],
                    execution_time_ms=result.execution_time_ms
                )

            except Exception as e:
                logger.error(f"Error processing Power Automate query: {str(e)}")
                return PowerAutomateQueryResponse(
                    success=False,
                    query=request.query,
                    answer="",
                    results=[],
                    execution_time_ms=0,
                    error=str(e)
                )

        @self.router.get("/workflows")
        async def list_workflows(
            authorization: Optional[str] = Header(None)
        ):
            """List available workflows for Power Automate"""
            if self.api_key:
                if not authorization or authorization != f"Bearer {self.api_key}":
                    raise HTTPException(status_code=401, detail="Invalid API key")

            workflows = self.workflow_router.list_workflows()

            return {
                "workflows": [
                    {
                        "id": wf.workflow_id,
                        "name": wf.name,
                        "description": wf.description,
                        "requires_roles": wf.required_roles
                    }
                    for wf in workflows
                    if wf.active
                ]
            }

        @self.router.get("/health")
        async def health_check():
            """Health check endpoint for Power Automate connector"""
            return {
                "status": "healthy",
                "service": "knowledge-system-power-automate",
                "workflows_available": len(self.workflow_router.list_workflows())
            }

    def get_router(self) -> APIRouter:
        """Get FastAPI router for integration"""
        return self.router

    def generate_connector_definition(self) -> Dict[str, Any]:
        """
        Generate Power Automate custom connector definition.

        Returns OpenAPI/Swagger definition for import into Power Automate.
        """
        return {
            "swagger": "2.0",
            "info": {
                "title": "Knowledge System Connector",
                "description": "Query organizational knowledge stores with RBAC and audit logging",
                "version": "1.0.0"
            },
            "host": "your-api-host.com",
            "basePath": "/power-automate",
            "schemes": ["https"],
            "consumes": ["application/json"],
            "produces": ["application/json"],
            "paths": {
                "/query": {
                    "post": {
                        "summary": "Query Knowledge Store",
                        "description": "Execute a workflow query against knowledge stores",
                        "operationId": "QueryKnowledge",
                        "parameters": [
                            {
                                "name": "body",
                                "in": "body",
                                "required": True,
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "query": {
                                            "type": "string",
                                            "description": "Query text"
                                        },
                                        "workflow_id": {
                                            "type": "string",
                                            "description": "Workflow ID"
                                        },
                                        "user_email": {
                                            "type": "string",
                                            "description": "User email"
                                        },
                                        "max_results": {
                                            "type": "integer",
                                            "description": "Maximum results"
                                        }
                                    },
                                    "required": ["query", "workflow_id", "user_email"]
                                }
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "Query results",
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {"type": "boolean"},
                                        "query": {"type": "string"},
                                        "answer": {"type": "string"},
                                        "results": {"type": "array"},
                                        "execution_time_ms": {"type": "number"}
                                    }
                                }
                            }
                        }
                    }
                },
                "/workflows": {
                    "get": {
                        "summary": "List Workflows",
                        "description": "Get available workflows",
                        "operationId": "ListWorkflows",
                        "responses": {
                            "200": {
                                "description": "List of workflows",
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "workflows": {"type": "array"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "securityDefinitions": {
                "api_key": {
                    "type": "apiKey",
                    "name": "Authorization",
                    "in": "header"
                }
            },
            "security": [{"api_key": []}]
        }
