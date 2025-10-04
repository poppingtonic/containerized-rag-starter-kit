"""
Workflow Router

Routes queries through appropriate workflows with permission gating.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from ..audit.logger import AuditLogger
from ..audit.models import EventType
from ..privacy.obfuscator import DataObfuscator
from ..privacy.models import SensitivityLevel
from ..rbac.service import RBACService
from ..stores.manager import KnowledgeStoreManager
from .models import Workflow, WorkflowContext, WorkflowQueryResult

logger = logging.getLogger(__name__)


class WorkflowRouter:
    """
    Routes queries through workflows with:
    - Permission checking
    - Knowledge store routing
    - PII obfuscation
    - Audit logging
    """

    def __init__(
        self,
        store_manager: KnowledgeStoreManager,
        rbac_service: RBACService,
        audit_logger: AuditLogger,
        obfuscator: DataObfuscator
    ):
        self.store_manager = store_manager
        self.rbac_service = rbac_service
        self.audit_logger = audit_logger
        self.obfuscator = obfuscator
        self.workflows: Dict[str, Workflow] = {}

    def register_workflow(self, workflow: Workflow) -> None:
        """
        Register a workflow.

        Args:
            workflow: Workflow definition
        """
        self.workflows[workflow.workflow_id] = workflow
        logger.info(f"Registered workflow: {workflow.name} ({workflow.workflow_id})")

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Get a workflow by ID"""
        return self.workflows.get(workflow_id)

    def list_workflows(self) -> List[Workflow]:
        """List all registered workflows"""
        return list(self.workflows.values())

    def get_accessible_workflows(self, user_roles: List[str]) -> List[Workflow]:
        """
        Get workflows accessible to a user based on roles.

        Args:
            user_roles: User's roles

        Returns:
            List of accessible workflows
        """
        accessible = []
        for workflow in self.workflows.values():
            if not workflow.active:
                continue

            # Check if user has required role
            if workflow.required_roles:
                if not any(role in user_roles for role in workflow.required_roles):
                    continue

            # Check if user has denied role
            if workflow.denied_roles:
                if any(role in user_roles for role in workflow.denied_roles):
                    continue

            accessible.append(workflow)

        return accessible

    async def execute_workflow(
        self,
        workflow_id: str,
        query: str,
        context: WorkflowContext
    ) -> WorkflowQueryResult:
        """
        Execute a query through a workflow.

        Args:
            workflow_id: ID of workflow to use
            query: Query text
            context: Workflow context with user info

        Returns:
            WorkflowQueryResult with results and metadata
        """
        start_time = time.time()

        # Get workflow
        workflow = self.workflows.get(workflow_id)
        if not workflow or not workflow.active:
            raise ValueError(f"Workflow not found or inactive: {workflow_id}")

        # Check user has access to workflow
        access_decision = self.rbac_service.check_workflow_access(
            context.user_id,
            workflow_id
        )

        if not access_decision.allowed:
            # Log denied access
            await self.audit_logger.log_permission_check(
                user_id=context.user_id,
                user_email=context.user_email,
                user_roles=context.user_roles,
                resource_type="workflow",
                resource_id=workflow_id,
                action="execute",
                allowed=False,
                reason=access_decision.reason,
                context=context.to_dict()
            )
            raise PermissionError(f"Access denied to workflow: {access_decision.reason}")

        # Sanitize query to prevent prompt injection
        sanitized_query = self._sanitize_query(query)

        # Query allowed stores
        stores_to_query = workflow.allowed_stores
        filters = workflow.default_filters.copy()

        # Execute query across stores
        store_results = await self.store_manager.query_stores(
            query_text=sanitized_query,
            user_id=context.user_id,
            user_roles=context.user_roles,
            store_ids=stores_to_query,
            max_results_per_store=workflow.max_results,
            filters=filters
        )

        # Aggregate results
        all_results = []
        for store_id, results in store_results.items():
            all_results.extend(results)

        # Sort by relevance
        all_results.sort(key=lambda r: r.similarity_score, reverse=True)
        top_results = all_results[:workflow.max_results]

        # Apply PII obfuscation if needed
        obfuscated = False
        if workflow.obfuscation_enabled:
            sensitivity = self._get_sensitivity_level(workflow.pii_level)
            for result in top_results:
                result.content = self.obfuscator.obfuscate(
                    result.content,
                    sensitivity,
                    preserve_structure=True
                )
                result.obfuscated = True
                obfuscated = True

        # Generate answer (simplified - would use QA service)
        answer = self._generate_answer(sanitized_query, top_results)

        # Log query execution
        if workflow.log_queries:
            await self.audit_logger.log_query(
                user_id=context.user_id,
                user_email=context.user_email,
                user_roles=context.user_roles,
                query_text=query if workflow.log_results else "[QUERY_LOGGED]",
                store_id=",".join(stores_to_query),
                results_count=len(top_results),
                workflow_id=workflow_id,
                context=context.to_dict()
            )

        execution_time = (time.time() - start_time) * 1000

        return WorkflowQueryResult(
            workflow_id=workflow_id,
            query=query,
            answer=answer,
            stores_queried=stores_to_query,
            total_results=len(top_results),
            results=[self._result_to_dict(r) for r in top_results],
            obfuscated=obfuscated,
            audit_logged=workflow.log_queries,
            execution_time_ms=execution_time
        )

    def _sanitize_query(self, query: str) -> str:
        """
        Sanitize query to prevent prompt injection.

        Args:
            query: Raw query text

        Returns:
            Sanitized query
        """
        # Remove potentially dangerous patterns
        dangerous_patterns = [
            "ignore previous instructions",
            "ignore all previous",
            "new instruction:",
            "system:",
            "<|im_start|>",
            "<|im_end|>",
        ]

        sanitized = query
        for pattern in dangerous_patterns:
            sanitized = sanitized.replace(pattern, "")

        # Limit length
        max_length = 1000
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]

        # Log if suspicious
        if sanitized != query:
            asyncio.create_task(
                self.audit_logger.log_security_event(
                    event_type=EventType.PROMPT_INJECTION_ATTEMPT,
                    user_id=None,
                    description=f"Suspicious query detected and sanitized",
                    suspicious=True,
                    context={"original_query": query, "sanitized_query": sanitized}
                )
            )

        return sanitized.strip()

    def _get_sensitivity_level(self, pii_level: str) -> SensitivityLevel:
        """Map PII level string to SensitivityLevel enum"""
        mapping = {
            "full": SensitivityLevel.PUBLIC,
            "partial": SensitivityLevel.CONFIDENTIAL,
            "metadata_only": SensitivityLevel.SECRET
        }
        return mapping.get(pii_level, SensitivityLevel.INTERNAL)

    def _generate_answer(self, query: str, results: List) -> str:
        """
        Generate answer from results.

        In production, this would use the QA service.
        """
        if not results:
            return "No results found for your query."

        # Simplified answer generation
        contexts = [r.content for r in results[:3]]
        context_text = "\n\n".join(contexts)

        return f"Based on the available information:\n\n{context_text[:500]}..."

    def _result_to_dict(self, result) -> Dict[str, Any]:
        """Convert QueryResult to dict"""
        return {
            "doc_id": result.doc_id,
            "store_id": result.store_id,
            "content": result.content,
            "similarity_score": result.similarity_score,
            "obfuscated": result.obfuscated,
            "metadata": {
                "title": result.metadata.title,
                "author": result.metadata.author,
                "created_at": result.metadata.created_at.isoformat() if result.metadata.created_at else None
            }
        }

    async def get_workflow_statistics(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get usage statistics for a workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Dict with statistics
        """
        # Would query audit logs for workflow statistics
        return {
            "workflow_id": workflow_id,
            "total_queries": 0,
            "unique_users": 0,
            "avg_results": 0,
            "avg_execution_time": 0
        }
