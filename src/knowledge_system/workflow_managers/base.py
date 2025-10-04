"""
Base Workflow Manager Interface

Abstract interface for external workflow management platforms.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class WorkflowExecutionResult:
    """Result from workflow execution"""
    workflow_id: str
    execution_id: str
    success: bool
    output: Any
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    steps_executed: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class WorkflowDefinition:
    """Workflow definition from external platform"""
    workflow_id: str
    name: str
    description: str
    version: str
    platform: str  # "langgraph_studio", "dify", etc.
    graph_definition: Dict[str, Any]  # Platform-specific graph structure
    variables: Dict[str, Any] = field(default_factory=dict)
    tools: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkflowManager(ABC):
    """
    Abstract base class for workflow management platforms.

    Integrates external workflow engines (LangGraph Studio, Dify, etc.)
    with the knowledge system's RBAC, audit, and PII protection.
    """

    def __init__(self, platform_name: str):
        self.platform_name = platform_name
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize connection to workflow platform.

        Returns:
            bool: True if initialization succeeded
        """
        pass

    @abstractmethod
    async def list_workflows(self) -> List[WorkflowDefinition]:
        """
        List available workflows from the platform.

        Returns:
            List of workflow definitions
        """
        pass

    @abstractmethod
    async def get_workflow(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        """
        Get a specific workflow definition.

        Args:
            workflow_id: Workflow identifier

        Returns:
            WorkflowDefinition or None
        """
        pass

    @abstractmethod
    async def execute_workflow(
        self,
        workflow_id: str,
        inputs: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> WorkflowExecutionResult:
        """
        Execute a workflow with given inputs.

        Args:
            workflow_id: Workflow to execute
            inputs: Input variables for the workflow
            user_context: User context (user_id, roles, etc.)

        Returns:
            WorkflowExecutionResult with output and metadata
        """
        pass

    @abstractmethod
    async def deploy_workflow(
        self,
        workflow_definition: WorkflowDefinition
    ) -> bool:
        """
        Deploy a workflow to the platform.

        Args:
            workflow_definition: Workflow to deploy

        Returns:
            bool: True if deployment succeeded
        """
        pass

    @abstractmethod
    async def update_workflow(
        self,
        workflow_id: str,
        workflow_definition: WorkflowDefinition
    ) -> bool:
        """
        Update an existing workflow.

        Args:
            workflow_id: Workflow to update
            workflow_definition: New workflow definition

        Returns:
            bool: True if update succeeded
        """
        pass

    @abstractmethod
    async def delete_workflow(self, workflow_id: str) -> bool:
        """
        Delete a workflow.

        Args:
            workflow_id: Workflow to delete

        Returns:
            bool: True if deletion succeeded
        """
        pass

    @abstractmethod
    async def get_execution_history(
        self,
        workflow_id: str,
        limit: int = 100
    ) -> List[WorkflowExecutionResult]:
        """
        Get execution history for a workflow.

        Args:
            workflow_id: Workflow identifier
            limit: Maximum number of executions to return

        Returns:
            List of execution results
        """
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of workflow platform connection.

        Returns:
            Dict with health status
        """
        pass

    def is_initialized(self) -> bool:
        """Check if manager is initialized"""
        return self._initialized

    def get_platform_name(self) -> str:
        """Get platform name"""
        return self.platform_name
