"""
Dify Integration

Integrates Dify for low-code workflow management.

Dify provides:
- Visual workflow builder
- Pre-built templates
- Built-in LLM integration
- API management
- Dataset management
- Multi-model support
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

from .base import WorkflowManager, WorkflowDefinition, WorkflowExecutionResult

logger = logging.getLogger(__name__)


class DifyWorkflowManager(WorkflowManager):
    """
    Dify workflow manager.

    Connects to Dify API to:
    - Load workflow apps
    - Execute workflows
    - Manage datasets
    - Monitor execution
    """

    def __init__(
        self,
        api_url: str,
        api_key: str,
        workspace_id: Optional[str] = None,
        timeout: int = 300
    ):
        """
        Initialize Dify manager.

        Args:
            api_url: Dify API endpoint (e.g., https://api.dify.ai/v1)
            api_key: Dify API key
            workspace_id: Optional workspace ID
            timeout: Request timeout in seconds
        """
        super().__init__("dify")
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.workspace_id = workspace_id
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None

    async def initialize(self) -> bool:
        """Initialize connection to Dify"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            self.session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )

            # Test connection by listing apps
            health = await self.health_check()
            if health.get("healthy"):
                self._initialized = True
                logger.info("Dify manager initialized")
                return True
            else:
                logger.error("Dify health check failed")
                return False

        except Exception as e:
            logger.error(f"Failed to initialize Dify: {str(e)}")
            return False

    async def list_workflows(self) -> List[WorkflowDefinition]:
        """
        List workflows (apps) from Dify.

        In Dify, workflows are called "apps" and can be:
        - Chatbot apps
        - Text generation apps
        - Agent apps
        - Workflow apps (DAG-based)
        """
        if not self.session:
            raise RuntimeError("Manager not initialized")

        try:
            # Dify API endpoint for listing apps
            url = f"{self.api_url}/apps"
            if self.workspace_id:
                url += f"?workspace_id={self.workspace_id}"

            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    workflows = []

                    for app_data in data.get("data", []):
                        # Convert Dify app to workflow definition
                        workflow = WorkflowDefinition(
                            workflow_id=app_data["id"],
                            name=app_data["name"],
                            description=app_data.get("description", ""),
                            version=app_data.get("version", "1.0"),
                            platform="dify",
                            graph_definition=app_data.get("model_config", {}),
                            variables=self._extract_variables(app_data),
                            tools=app_data.get("tools", []),
                            created_at=self._parse_datetime(app_data.get("created_at")),
                            updated_at=self._parse_datetime(app_data.get("updated_at")),
                            metadata={
                                "mode": app_data.get("mode", "workflow"),
                                "icon": app_data.get("icon", ""),
                                "icon_background": app_data.get("icon_background", ""),
                                "enable_site": app_data.get("enable_site", False),
                                "enable_api": app_data.get("enable_api", True)
                            }
                        )
                        workflows.append(workflow)

                    return workflows
                else:
                    logger.error(f"Failed to list workflows: {response.status}")
                    return []

        except Exception as e:
            logger.error(f"Error listing workflows: {str(e)}")
            return []

    async def get_workflow(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        """Get a specific workflow (app) from Dify"""
        if not self.session:
            raise RuntimeError("Manager not initialized")

        try:
            async with self.session.get(
                f"{self.api_url}/apps/{workflow_id}"
            ) as response:
                if response.status == 200:
                    app_data = await response.json()
                    data = app_data.get("data", app_data)

                    return WorkflowDefinition(
                        workflow_id=data["id"],
                        name=data["name"],
                        description=data.get("description", ""),
                        version=data.get("version", "1.0"),
                        platform="dify",
                        graph_definition=data.get("model_config", {}),
                        variables=self._extract_variables(data),
                        tools=data.get("tools", []),
                        created_at=self._parse_datetime(data.get("created_at")),
                        updated_at=self._parse_datetime(data.get("updated_at")),
                        metadata={
                            "mode": data.get("mode", "workflow"),
                            "icon": data.get("icon", ""),
                            "enable_site": data.get("enable_site", False),
                            "enable_api": data.get("enable_api", True)
                        }
                    )
                else:
                    logger.error(f"Workflow not found: {workflow_id}")
                    return None

        except Exception as e:
            logger.error(f"Error getting workflow: {str(e)}")
            return None

    async def execute_workflow(
        self,
        workflow_id: str,
        inputs: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> WorkflowExecutionResult:
        """
        Execute a Dify workflow.

        Dify workflows support:
        - Single execution (one-shot)
        - Conversational (stateful chat)
        - Streaming responses
        """
        if not self.session:
            raise RuntimeError("Manager not initialized")

        start_time = datetime.utcnow()

        try:
            # Prepare execution request for Dify
            # Dify uses different endpoints based on app mode
            execution_request = {
                "inputs": inputs,
                "response_mode": "blocking",  # or "streaming"
                "user": user_context.get("user_id", "default_user")
            }

            # Add conversation_id if provided (for stateful chat)
            if "conversation_id" in user_context:
                execution_request["conversation_id"] = user_context["conversation_id"]

            # Execute via Dify's completion API
            async with self.session.post(
                f"{self.api_url}/workflows/run",
                json=execution_request,
                headers={"Authorization": f"Bearer {workflow_id}"}  # Dify uses workflow ID as token
            ) as response:
                if response.status == 200:
                    result_data = await response.json()

                    execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                    # Extract output based on Dify response format
                    output = result_data.get("data", {}).get("outputs", {})
                    if not output:
                        output = result_data.get("answer", "")

                    return WorkflowExecutionResult(
                        workflow_id=workflow_id,
                        execution_id=result_data.get("task_id", ""),
                        success=True,
                        output=output,
                        execution_time_ms=execution_time,
                        steps_executed=result_data.get("workflow_run_id", []),
                        metadata={
                            "platform": "dify",
                            "conversation_id": result_data.get("conversation_id"),
                            "message_id": result_data.get("message_id"),
                            "tokens_used": result_data.get("metadata", {}).get("usage", {})
                        }
                    )
                else:
                    error_data = await response.json()
                    error_msg = error_data.get("message", f"HTTP {response.status}")

                    return WorkflowExecutionResult(
                        workflow_id=workflow_id,
                        execution_id="",
                        success=False,
                        output=None,
                        error=error_msg,
                        execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
                    )

        except Exception as e:
            logger.error(f"Error executing workflow: {str(e)}")
            return WorkflowExecutionResult(
                workflow_id=workflow_id,
                execution_id="",
                success=False,
                output=None,
                error=str(e),
                execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
            )

    async def deploy_workflow(self, workflow_definition: WorkflowDefinition) -> bool:
        """
        Deploy a workflow to Dify.

        Note: Dify workflows are typically created via the UI.
        This method supports programmatic deployment if API supports it.
        """
        if not self.session:
            raise RuntimeError("Manager not initialized")

        try:
            deployment_data = {
                "name": workflow_definition.name,
                "description": workflow_definition.description,
                "mode": workflow_definition.metadata.get("mode", "workflow"),
                "model_config": workflow_definition.graph_definition,
                "icon": workflow_definition.metadata.get("icon", "🤖"),
                "icon_background": workflow_definition.metadata.get("icon_background", "#FFEAD5")
            }

            async with self.session.post(
                f"{self.api_url}/apps",
                json=deployment_data
            ) as response:
                if response.status in [200, 201]:
                    logger.info(f"Deployed workflow: {workflow_definition.name}")
                    return True
                else:
                    logger.error(f"Failed to deploy workflow: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"Error deploying workflow: {str(e)}")
            return False

    async def update_workflow(
        self,
        workflow_id: str,
        workflow_definition: WorkflowDefinition
    ) -> bool:
        """Update an existing workflow in Dify"""
        if not self.session:
            raise RuntimeError("Manager not initialized")

        try:
            update_data = {
                "name": workflow_definition.name,
                "description": workflow_definition.description,
                "model_config": workflow_definition.graph_definition
            }

            async with self.session.put(
                f"{self.api_url}/apps/{workflow_id}",
                json=update_data
            ) as response:
                if response.status == 200:
                    logger.info(f"Updated workflow: {workflow_id}")
                    return True
                else:
                    logger.error(f"Failed to update workflow: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"Error updating workflow: {str(e)}")
            return False

    async def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow from Dify"""
        if not self.session:
            raise RuntimeError("Manager not initialized")

        try:
            async with self.session.delete(
                f"{self.api_url}/apps/{workflow_id}"
            ) as response:
                if response.status == 200:
                    logger.info(f"Deleted workflow: {workflow_id}")
                    return True
                else:
                    logger.error(f"Failed to delete workflow: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"Error deleting workflow: {str(e)}")
            return False

    async def get_execution_history(
        self,
        workflow_id: str,
        limit: int = 100
    ) -> List[WorkflowExecutionResult]:
        """
        Get execution history for a workflow.

        In Dify, this queries message/conversation history.
        """
        if not self.session:
            raise RuntimeError("Manager not initialized")

        try:
            async with self.session.get(
                f"{self.api_url}/messages",
                params={
                    "app_id": workflow_id,
                    "limit": limit
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    executions = []

                    for msg_data in data.get("data", []):
                        execution = WorkflowExecutionResult(
                            workflow_id=workflow_id,
                            execution_id=msg_data.get("id", ""),
                            success=True,
                            output=msg_data.get("answer", ""),
                            execution_time_ms=msg_data.get("provider_response_latency", 0) * 1000,
                            metadata={
                                "conversation_id": msg_data.get("conversation_id"),
                                "tokens": msg_data.get("message_tokens", 0),
                                "feedback": msg_data.get("feedback")
                            },
                            timestamp=self._parse_datetime(msg_data.get("created_at"))
                        )
                        executions.append(execution)

                    return executions
                else:
                    logger.error(f"Failed to get execution history: {response.status}")
                    return []

        except Exception as e:
            logger.error(f"Error getting execution history: {str(e)}")
            return []

    async def health_check(self) -> Dict[str, Any]:
        """Check Dify health"""
        if not self.session:
            return {"healthy": False, "error": "Not initialized"}

        try:
            # Dify doesn't have a dedicated health endpoint
            # We'll try to list apps as a health check
            async with self.session.get(f"{self.api_url}/apps", params={"limit": 1}) as response:
                if response.status == 200:
                    return {
                        "healthy": True,
                        "platform": "dify"
                    }
                else:
                    return {"healthy": False, "error": f"HTTP {response.status}"}

        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def shutdown(self):
        """Shutdown the manager and close connections"""
        if self.session:
            await self.session.close()
            self.session = None
        self._initialized = False
        logger.info("Dify manager shut down")

    def _extract_variables(self, app_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract input variables from Dify app config"""
        model_config = app_data.get("model_config", {})
        user_input_form = model_config.get("user_input_form", [])

        variables = {}
        for field in user_input_form:
            var_name = field.get("variable")
            if var_name:
                variables[var_name] = {
                    "type": field.get("type", "text"),
                    "label": field.get("label", var_name),
                    "required": field.get("required", False),
                    "default": field.get("default", "")
                }

        return variables

    def _parse_datetime(self, timestamp: Optional[Any]) -> datetime:
        """Parse datetime from Dify timestamp"""
        if not timestamp:
            return datetime.utcnow()

        try:
            if isinstance(timestamp, (int, float)):
                return datetime.fromtimestamp(timestamp)
            elif isinstance(timestamp, str):
                return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                return datetime.utcnow()
        except:
            return datetime.utcnow()
