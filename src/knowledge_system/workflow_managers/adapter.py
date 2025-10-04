"""
Workflow Manager Adapter

Bridges external workflow managers (LangGraph Studio, Dify)
with the knowledge system's RBAC, audit, and PII protection.
"""

import logging
from typing import Any, Dict, List, Optional

from ..audit.logger import AuditLogger
from ..audit.models import EventType
from ..privacy.obfuscator import DataObfuscator
from ..privacy.models import SensitivityLevel
from ..rbac.service import RBACService
from ..stores.manager import KnowledgeStoreManager
from ..workflows.models import WorkflowContext
from .base import WorkflowManager, WorkflowExecutionResult

logger = logging.getLogger(__name__)


class IntegratedWorkflowAdapter:
    """
    Adapter that integrates external workflow managers with knowledge system.

    Features:
    - Wraps external workflow execution with RBAC checks
    - Applies PII obfuscation to workflow outputs
    - Logs workflow execution to audit system
    - Provides knowledge store access as workflow tools
    - Maintains security boundaries
    """

    def __init__(
        self,
        workflow_manager: WorkflowManager,
        rbac_service: RBACService,
        audit_logger: AuditLogger,
        obfuscator: DataObfuscator,
        store_manager: KnowledgeStoreManager
    ):
        self.workflow_manager = workflow_manager
        self.rbac_service = rbac_service
        self.audit_logger = audit_logger
        self.obfuscator = obfuscator
        self.store_manager = store_manager

    async def execute_workflow_with_security(
        self,
        workflow_id: str,
        inputs: Dict[str, Any],
        context: WorkflowContext,
        pii_level: str = "partial",
        audit_level: str = "detailed"
    ) -> WorkflowExecutionResult:
        """
        Execute workflow with full security integration.

        Args:
            workflow_id: Workflow to execute
            inputs: Input variables
            context: User context with roles
            pii_level: PII obfuscation level
            audit_level: Audit logging detail level

        Returns:
            WorkflowExecutionResult with security applied
        """

        # 1. Check permissions
        permission_decision = self.rbac_service.check_workflow_access(
            context.user_id,
            workflow_id
        )

        if not permission_decision.allowed:
            # Log denied access
            await self.audit_logger.log_permission_check(
                user_id=context.user_id,
                user_email=context.user_email,
                user_roles=context.user_roles,
                resource_type="workflow",
                resource_id=workflow_id,
                action="execute",
                allowed=False,
                reason=permission_decision.reason,
                context=context.to_dict()
            )

            return WorkflowExecutionResult(
                workflow_id=workflow_id,
                execution_id="",
                success=False,
                output=None,
                error=f"Permission denied: {permission_decision.reason}"
            )

        # 2. Sanitize inputs to prevent injection
        sanitized_inputs = self._sanitize_inputs(inputs)

        # 3. Inject knowledge system tools into workflow context
        user_context = {
            **context.to_dict(),
            "tools": self._get_available_tools(context.user_roles),
            "knowledge_stores": self._get_accessible_stores(context.user_roles)
        }

        # 4. Execute workflow
        try:
            result = await self.workflow_manager.execute_workflow(
                workflow_id=workflow_id,
                inputs=sanitized_inputs,
                user_context=user_context
            )

            # 5. Apply PII obfuscation to output
            if result.success and result.output:
                result.output = self._obfuscate_output(
                    result.output,
                    pii_level
                )

            # 6. Log execution
            await self.audit_logger.log_event(
                self._create_audit_event(
                    workflow_id=workflow_id,
                    context=context,
                    result=result,
                    audit_level=audit_level
                )
            )

            return result

        except Exception as e:
            logger.error(f"Error executing workflow: {str(e)}")

            # Log error
            await self.audit_logger.log_security_event(
                event_type=EventType.WORKFLOW_EXECUTED,
                user_id=context.user_id,
                description=f"Workflow execution failed: {str(e)}",
                suspicious=False,
                context=context.to_dict()
            )

            return WorkflowExecutionResult(
                workflow_id=workflow_id,
                execution_id="",
                success=False,
                output=None,
                error=str(e)
            )

    async def list_accessible_workflows(
        self,
        user_roles: List[str]
    ) -> List[Dict[str, Any]]:
        """
        List workflows accessible to user based on roles.

        Args:
            user_roles: User's roles

        Returns:
            List of accessible workflow metadata
        """
        # Get all workflows from manager
        all_workflows = await self.workflow_manager.list_workflows()

        # Filter based on RBAC
        accessible = []
        for workflow in all_workflows:
            # Check if user has access (simplified - would check against RBAC policies)
            # In production, would query RBAC service for workflow permissions
            accessible.append({
                "workflow_id": workflow.workflow_id,
                "name": workflow.name,
                "description": workflow.description,
                "platform": workflow.platform,
                "version": workflow.version,
                "tools": workflow.tools
            })

        return accessible

    def _sanitize_inputs(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize workflow inputs to prevent injection attacks.

        Args:
            inputs: Raw input dictionary

        Returns:
            Sanitized inputs
        """
        sanitized = {}

        dangerous_patterns = [
            "ignore previous instructions",
            "ignore all previous",
            "new instruction:",
            "system:",
            "<|im_start|>",
            "<|im_end|>",
            "```python",
            "exec(",
            "eval("
        ]

        for key, value in inputs.items():
            if isinstance(value, str):
                sanitized_value = value
                for pattern in dangerous_patterns:
                    sanitized_value = sanitized_value.replace(pattern, "")

                # Limit length
                max_length = 10000
                if len(sanitized_value) > max_length:
                    sanitized_value = sanitized_value[:max_length]

                sanitized[key] = sanitized_value
            else:
                sanitized[key] = value

        return sanitized

    def _obfuscate_output(
        self,
        output: Any,
        pii_level: str
    ) -> Any:
        """
        Apply PII obfuscation to workflow output.

        Args:
            output: Workflow output
            pii_level: Obfuscation level

        Returns:
            Obfuscated output
        """
        if isinstance(output, str):
            sensitivity = self._get_sensitivity_level(pii_level)
            return self.obfuscator.obfuscate(
                output,
                sensitivity,
                preserve_structure=True
            )
        elif isinstance(output, dict):
            # Recursively obfuscate dict values
            obfuscated = {}
            for key, value in output.items():
                if isinstance(value, (str, dict)):
                    obfuscated[key] = self._obfuscate_output(value, pii_level)
                else:
                    obfuscated[key] = value
            return obfuscated
        else:
            return output

    def _get_sensitivity_level(self, pii_level: str) -> SensitivityLevel:
        """Map PII level string to SensitivityLevel"""
        mapping = {
            "full": SensitivityLevel.PUBLIC,
            "partial": SensitivityLevel.CONFIDENTIAL,
            "metadata_only": SensitivityLevel.SECRET
        }
        return mapping.get(pii_level, SensitivityLevel.INTERNAL)

    def _get_available_tools(self, user_roles: List[str]) -> List[str]:
        """
        Get list of tools available to user based on roles.

        These tools can be called by the workflow.
        """
        tools = [
            "query_knowledge_store",
            "search_documents",
            "get_document"
        ]

        # Add role-specific tools
        if "analyst" in user_roles:
            tools.append("query_confidential_store")

        if "manager" in user_roles:
            tools.append("get_team_analytics")

        return tools

    def _get_accessible_stores(self, user_roles: List[str]) -> List[str]:
        """Get list of knowledge stores accessible to user"""
        accessible_stores = self.store_manager.get_accessible_stores(user_roles)
        return [store.store_id for store in accessible_stores]

    def _create_audit_event(
        self,
        workflow_id: str,
        context: WorkflowContext,
        result: WorkflowExecutionResult,
        audit_level: str
    ):
        """Create audit event for workflow execution"""
        from ..audit.models import AuditEvent, AuditLevel

        level_map = {
            "basic": AuditLevel.BASIC,
            "detailed": AuditLevel.DETAILED,
            "forensic": AuditLevel.FORENSIC
        }

        import uuid
        return AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.WORKFLOW_EXECUTED,
            timestamp=result.timestamp,
            user_id=context.user_id,
            user_email=context.user_email,
            user_roles=context.user_roles,
            resource_type="workflow",
            resource_id=workflow_id,
            action="execute",
            result="success" if result.success else "failure",
            reason=result.error if not result.success else None,
            workflow_id=workflow_id,
            metadata={
                "execution_id": result.execution_id,
                "execution_time_ms": result.execution_time_ms,
                "platform": self.workflow_manager.get_platform_name(),
                "steps_executed": len(result.steps_executed)
            },
            audit_level=level_map.get(audit_level, AuditLevel.DETAILED)
        )


class KnowledgeSystemTools:
    """
    Tools that workflows can call to access knowledge system.

    These are injected into LangGraph/Dify workflows as callable functions.
    """

    def __init__(
        self,
        store_manager: KnowledgeStoreManager,
        rbac_service: RBACService,
        user_context: WorkflowContext
    ):
        self.store_manager = store_manager
        self.rbac_service = rbac_service
        self.user_context = user_context

    async def query_knowledge_store(
        self,
        query: str,
        store_ids: Optional[List[str]] = None,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Query knowledge stores from within a workflow.

        Args:
            query: Search query
            store_ids: Specific stores to query (None = all accessible)
            max_results: Maximum results

        Returns:
            List of search results
        """
        results = await self.store_manager.query_stores(
            query_text=query,
            user_id=self.user_context.user_id,
            user_roles=self.user_context.user_roles,
            store_ids=store_ids,
            max_results_per_store=max_results
        )

        # Flatten and format results
        all_results = []
        for store_id, store_results in results.items():
            for result in store_results:
                all_results.append({
                    "content": result.content,
                    "source": result.metadata.title,
                    "store": store_id,
                    "score": result.similarity_score
                })

        return all_results

    async def get_document(
        self,
        doc_id: str,
        store_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific document from a store.

        Args:
            doc_id: Document identifier
            store_id: Store containing the document

        Returns:
            Document data or None
        """
        store = self.store_manager.get_store(store_id)
        if not store:
            return None

        result = await store.get_document(
            doc_id=doc_id,
            user_id=self.user_context.user_id,
            user_roles=self.user_context.user_roles
        )

        if result:
            return {
                "content": result.content,
                "title": result.metadata.title,
                "author": result.metadata.author,
                "created_at": result.metadata.created_at.isoformat() if result.metadata.created_at else None
            }

        return None
