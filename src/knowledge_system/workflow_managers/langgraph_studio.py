"""
LangGraph Studio Integration

Integrates LangGraph Studio for visual graph-based workflow management.

LangGraph Studio provides:
- Visual workflow design with drag-and-drop
- State management for complex workflows
- Built-in agent nodes
- Checkpointing and recovery
- Real-time debugging
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

from .base import WorkflowManager, WorkflowDefinition, WorkflowExecutionResult

logger = logging.getLogger(__name__)


class LangGraphStudioManager(WorkflowManager):
    """
    LangGraph Studio workflow manager.

    Connects to LangGraph Studio API to:
    - Load workflow graphs
    - Execute workflows with state management
    - Monitor execution progress
    - Access execution history
    """

    def __init__(
        self,
        api_url: str,
        api_key: Optional[str] = None,
        timeout: int = 300
    ):
        """
        Initialize LangGraph Studio manager.

        Args:
            api_url: LangGraph Studio API endpoint
            api_key: API key for authentication
            timeout: Request timeout in seconds
        """
        super().__init__("langgraph_studio")
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None

    async def initialize(self) -> bool:
        """Initialize connection to LangGraph Studio"""
        try:
            # Create aiohttp session
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            headers["Content-Type"] = "application/json"

            self.session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )

            # Test connection
            health = await self.health_check()
            if health.get("healthy"):
                self._initialized = True
                logger.info("LangGraph Studio manager initialized")
                return True
            else:
                logger.error("LangGraph Studio health check failed")
                return False

        except Exception as e:
            logger.error(f"Failed to initialize LangGraph Studio: {str(e)}")
            return False

    async def list_workflows(self) -> List[WorkflowDefinition]:
        """List workflows from LangGraph Studio"""
        if not self.session:
            raise RuntimeError("Manager not initialized")

        try:
            async with self.session.get(f"{self.api_url}/workflows") as response:
                if response.status == 200:
                    data = await response.json()
                    workflows = []

                    for wf_data in data.get("workflows", []):
                        workflow = WorkflowDefinition(
                            workflow_id=wf_data["id"],
                            name=wf_data["name"],
                            description=wf_data.get("description", ""),
                            version=wf_data.get("version", "1.0"),
                            platform="langgraph_studio",
                            graph_definition=wf_data.get("graph", {}),
                            variables=wf_data.get("variables", {}),
                            tools=wf_data.get("tools", []),
                            created_at=self._parse_datetime(wf_data.get("created_at")),
                            updated_at=self._parse_datetime(wf_data.get("updated_at")),
                            metadata=wf_data.get("metadata", {})
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
        """Get a specific workflow from LangGraph Studio"""
        if not self.session:
            raise RuntimeError("Manager not initialized")

        try:
            async with self.session.get(
                f"{self.api_url}/workflows/{workflow_id}"
            ) as response:
                if response.status == 200:
                    wf_data = await response.json()
                    return WorkflowDefinition(
                        workflow_id=wf_data["id"],
                        name=wf_data["name"],
                        description=wf_data.get("description", ""),
                        version=wf_data.get("version", "1.0"),
                        platform="langgraph_studio",
                        graph_definition=wf_data.get("graph", {}),
                        variables=wf_data.get("variables", {}),
                        tools=wf_data.get("tools", []),
                        created_at=self._parse_datetime(wf_data.get("created_at")),
                        updated_at=self._parse_datetime(wf_data.get("updated_at")),
                        metadata=wf_data.get("metadata", {})
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
        Execute a LangGraph Studio workflow.

        LangGraph workflows are stateful graphs that can:
        - Execute nodes sequentially or in parallel
        - Maintain state across steps
        - Handle conditional branching
        - Support checkpointing for recovery
        """
        if not self.session:
            raise RuntimeError("Manager not initialized")

        start_time = datetime.utcnow()

        try:
            # Prepare execution request
            execution_request = {
                "workflow_id": workflow_id,
                "inputs": inputs,
                "context": user_context,
                "config": {
                    "checkpointing": True,
                    "stream": False  # Set to True for streaming execution
                }
            }

            # Execute workflow
            async with self.session.post(
                f"{self.api_url}/workflows/{workflow_id}/execute",
                json=execution_request
            ) as response:
                if response.status == 200:
                    result_data = await response.json()

                    execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                    return WorkflowExecutionResult(
                        workflow_id=workflow_id,
                        execution_id=result_data.get("execution_id", ""),
                        success=True,
                        output=result_data.get("output"),
                        execution_time_ms=execution_time,
                        steps_executed=result_data.get("steps", []),
                        metadata={
                            "platform": "langgraph_studio",
                            "checkpoints": result_data.get("checkpoints", []),
                            "final_state": result_data.get("final_state", {})
                        }
                    )
                else:
                    error_data = await response.json()
                    error_msg = error_data.get("error", f"HTTP {response.status}")

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
        """Deploy a workflow to LangGraph Studio"""
        if not self.session:
            raise RuntimeError("Manager not initialized")

        try:
            deployment_data = {
                "name": workflow_definition.name,
                "description": workflow_definition.description,
                "version": workflow_definition.version,
                "graph": workflow_definition.graph_definition,
                "variables": workflow_definition.variables,
                "tools": workflow_definition.tools,
                "metadata": workflow_definition.metadata
            }

            async with self.session.post(
                f"{self.api_url}/workflows",
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
        """Update an existing workflow in LangGraph Studio"""
        if not self.session:
            raise RuntimeError("Manager not initialized")

        try:
            update_data = {
                "name": workflow_definition.name,
                "description": workflow_definition.description,
                "version": workflow_definition.version,
                "graph": workflow_definition.graph_definition,
                "variables": workflow_definition.variables,
                "tools": workflow_definition.tools,
                "metadata": workflow_definition.metadata
            }

            async with self.session.put(
                f"{self.api_url}/workflows/{workflow_id}",
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
        """Delete a workflow from LangGraph Studio"""
        if not self.session:
            raise RuntimeError("Manager not initialized")

        try:
            async with self.session.delete(
                f"{self.api_url}/workflows/{workflow_id}"
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
        """Get execution history for a workflow"""
        if not self.session:
            raise RuntimeError("Manager not initialized")

        try:
            async with self.session.get(
                f"{self.api_url}/workflows/{workflow_id}/executions",
                params={"limit": limit}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    executions = []

                    for exec_data in data.get("executions", []):
                        execution = WorkflowExecutionResult(
                            workflow_id=workflow_id,
                            execution_id=exec_data["id"],
                            success=exec_data["success"],
                            output=exec_data.get("output"),
                            error=exec_data.get("error"),
                            execution_time_ms=exec_data.get("execution_time_ms", 0),
                            steps_executed=exec_data.get("steps", []),
                            metadata=exec_data.get("metadata", {}),
                            timestamp=self._parse_datetime(exec_data.get("timestamp"))
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
        """Check LangGraph Studio health"""
        if not self.session:
            return {"healthy": False, "error": "Not initialized"}

        try:
            async with self.session.get(f"{self.api_url}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "healthy": True,
                        "platform": "langgraph_studio",
                        "version": data.get("version", "unknown")
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
        logger.info("LangGraph Studio manager shut down")

    def _parse_datetime(self, dt_string: Optional[str]) -> datetime:
        """Parse datetime string"""
        if not dt_string:
            return datetime.utcnow()
        try:
            return datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        except:
            return datetime.utcnow()
