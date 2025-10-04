"""
Workflow Manager Integrations

Support for external workflow management platforms:
- LangGraph Studio: Visual graph-based workflows
- Dify: Low-code workflow builder
- Custom workflow engines
"""

from .base import WorkflowManager, WorkflowExecutionResult
from .langgraph_studio import LangGraphStudioManager
from .dify import DifyWorkflowManager

__all__ = [
    "WorkflowManager",
    "WorkflowExecutionResult",
    "LangGraphStudioManager",
    "DifyWorkflowManager",
]
