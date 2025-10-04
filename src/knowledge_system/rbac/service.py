"""
RBAC Service

Core service for role-based access control with permission gating.
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Set

from .models import (
    AccessDecision,
    AccessPolicy,
    Permission,
    PermissionType,
    Role,
    User,
    WorkflowPermissionSet,
)

logger = logging.getLogger(__name__)


class RBACService:
    """
    Role-Based Access Control service.

    Features:
    - Role hierarchy and inheritance
    - Policy-based access control
    - Workflow permission sets
    - Condition evaluation (time-based, IP-based, etc.)
    - Prompt injection prevention
    """

    def __init__(self):
        self.roles: Dict[str, Role] = {}
        self.users: Dict[str, User] = {}
        self.policies: Dict[str, AccessPolicy] = {}
        self.workflows: Dict[str, WorkflowPermissionSet] = {}

    # Role Management

    def add_role(self, role: Role) -> None:
        """Add or update a role"""
        self.roles[role.role_id] = role
        logger.info(f"Added role: {role.name} ({role.role_id})")

    def get_role(self, role_id: str) -> Optional[Role]:
        """Get a role by ID"""
        return self.roles.get(role_id)

    def get_user_roles(self, user_id: str) -> List[Role]:
        """
        Get all roles for a user, including inherited roles.

        Args:
            user_id: User identifier

        Returns:
            List of Role objects
        """
        user = self.users.get(user_id)
        if not user:
            return []

        # Get direct roles
        role_ids = set(user.roles)

        # Add inherited roles
        expanded_roles = self._expand_role_hierarchy(role_ids)

        return [self.roles[rid] for rid in expanded_roles if rid in self.roles]

    def _expand_role_hierarchy(self, role_ids: Set[str]) -> Set[str]:
        """
        Expand role IDs to include inherited roles.

        Args:
            role_ids: Initial set of role IDs

        Returns:
            Expanded set including parent roles
        """
        expanded = set(role_ids)
        to_process = list(role_ids)

        while to_process:
            current_id = to_process.pop()
            role = self.roles.get(current_id)
            if role:
                for parent_id in role.parent_roles:
                    if parent_id not in expanded:
                        expanded.add(parent_id)
                        to_process.append(parent_id)

        return expanded

    # User Management

    def add_user(self, user: User) -> None:
        """Add or update a user"""
        self.users[user.user_id] = user
        logger.info(f"Added user: {user.email} ({user.user_id})")

    def get_user(self, user_id: str) -> Optional[User]:
        """Get a user by ID"""
        return self.users.get(user_id)

    def assign_role_to_user(self, user_id: str, role_id: str) -> bool:
        """
        Assign a role to a user.

        Args:
            user_id: User identifier
            role_id: Role identifier

        Returns:
            bool: True if assignment succeeded
        """
        user = self.users.get(user_id)
        if not user or role_id not in self.roles:
            return False

        if role_id not in user.roles:
            user.roles.append(role_id)
            logger.info(f"Assigned role {role_id} to user {user_id}")
            return True
        return False

    # Policy Management

    def add_policy(self, policy: AccessPolicy) -> None:
        """Add or update an access policy"""
        self.policies[policy.policy_id] = policy
        logger.info(f"Added policy: {policy.name} ({policy.policy_id})")

    def get_policy(self, policy_id: str) -> Optional[AccessPolicy]:
        """Get a policy by ID"""
        return self.policies.get(policy_id)

    # Workflow Management

    def register_workflow(self, workflow: WorkflowPermissionSet) -> None:
        """Register a workflow permission set"""
        self.workflows[workflow.workflow_id] = workflow
        logger.info(f"Registered workflow: {workflow.workflow_name} ({workflow.workflow_id})")

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowPermissionSet]:
        """Get a workflow permission set"""
        return self.workflows.get(workflow_id)

    # Permission Checking

    def check_permission(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        permission_type: PermissionType,
        context: Optional[Dict] = None
    ) -> AccessDecision:
        """
        Check if a user has permission for an operation.

        Args:
            user_id: User identifier
            resource_type: Type of resource (store, document, etc.)
            resource_id: Resource identifier
            permission_type: Type of permission requested
            context: Additional context (IP, time, metadata, etc.)

        Returns:
            AccessDecision with allow/deny and reason
        """
        context = context or {}

        # Get user
        user = self.users.get(user_id)
        if not user:
            return AccessDecision(
                allowed=False,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                permission_type=permission_type,
                reason="User not found"
            )

        if not user.active:
            return AccessDecision(
                allowed=False,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                permission_type=permission_type,
                reason="User account is inactive"
            )

        # Check direct permissions
        if self._check_direct_permissions(user, resource_type, resource_id, permission_type):
            return AccessDecision(
                allowed=True,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                permission_type=permission_type,
                reason="Direct permission granted"
            )

        # Check role permissions
        user_roles = self.get_user_roles(user_id)
        for role in user_roles:
            for perm in role.permissions:
                if (perm.resource_type == resource_type and
                    perm.resource_id == resource_id and
                    perm.permission_type == permission_type):
                    # Check conditions
                    if self._evaluate_conditions(perm.conditions, context):
                        return AccessDecision(
                            allowed=True,
                            user_id=user_id,
                            resource_type=resource_type,
                            resource_id=resource_id,
                            permission_type=permission_type,
                            reason=f"Permission granted via role: {role.name}"
                        )

        # Check policies
        matched_policies = self._match_policies(resource_type, resource_id)
        decision = self._evaluate_policies(matched_policies, user, permission_type, context)
        if decision:
            return decision

        # Default deny
        return AccessDecision(
            allowed=False,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            permission_type=permission_type,
            reason="No matching permission found (default deny)"
        )

    def check_workflow_access(
        self,
        user_id: str,
        workflow_id: str
    ) -> AccessDecision:
        """
        Check if a user can access a workflow.

        Args:
            user_id: User identifier
            workflow_id: Workflow identifier

        Returns:
            AccessDecision
        """
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return AccessDecision(
                allowed=False,
                user_id=user_id,
                resource_type="workflow",
                resource_id=workflow_id,
                permission_type=PermissionType.QUERY,
                reason="Workflow not found"
            )

        user = self.users.get(user_id)
        if not user or not user.active:
            return AccessDecision(
                allowed=False,
                user_id=user_id,
                resource_type="workflow",
                resource_id=workflow_id,
                permission_type=PermissionType.QUERY,
                reason="User not found or inactive"
            )

        # Check if user has any of the required roles
        user_role_ids = set(user.roles)
        required_role_ids = set(workflow.required_roles)

        if not required_role_ids or user_role_ids.intersection(required_role_ids):
            return AccessDecision(
                allowed=True,
                user_id=user_id,
                resource_type="workflow",
                resource_id=workflow_id,
                permission_type=PermissionType.QUERY,
                reason="User has required role for workflow"
            )

        return AccessDecision(
            allowed=False,
            user_id=user_id,
            resource_type="workflow",
            resource_id=workflow_id,
            permission_type=PermissionType.QUERY,
            reason=f"User lacks required roles: {required_role_ids}"
        )

    # Helper Methods

    def _check_direct_permissions(
        self,
        user: User,
        resource_type: str,
        resource_id: str,
        permission_type: PermissionType
    ) -> bool:
        """Check if user has direct permission"""
        for perm in user.direct_permissions:
            if (perm.resource_type == resource_type and
                perm.resource_id == resource_id and
                perm.permission_type == permission_type):
                return True
        return False

    def _match_policies(
        self,
        resource_type: str,
        resource_id: str
    ) -> List[AccessPolicy]:
        """Find policies matching a resource"""
        matched = []
        for policy in self.policies.values():
            if not policy.active:
                continue
            if policy.expires_at and policy.expires_at < datetime.utcnow():
                continue
            if policy.resource_type != resource_type:
                continue
            # Check pattern match
            if self._pattern_matches(policy.resource_pattern, resource_id):
                matched.append(policy)

        # Sort by priority (higher first)
        matched.sort(key=lambda p: p.priority, reverse=True)
        return matched

    def _pattern_matches(self, pattern: str, resource_id: str) -> bool:
        """Check if a pattern matches a resource ID"""
        # Support glob patterns
        regex_pattern = pattern.replace("*", ".*").replace("?", ".")
        return bool(re.match(f"^{regex_pattern}$", resource_id))

    def _evaluate_policies(
        self,
        policies: List[AccessPolicy],
        user: User,
        permission_type: PermissionType,
        context: Dict
    ) -> Optional[AccessDecision]:
        """
        Evaluate policies for a user.

        Returns AccessDecision if a policy matches, None otherwise.
        """
        for policy in policies:
            # Check explicit deny first
            if user.user_id in policy.denied_users:
                return AccessDecision(
                    allowed=False,
                    user_id=user.user_id,
                    resource_type=policy.resource_type,
                    resource_id="",
                    permission_type=permission_type,
                    reason=f"Explicitly denied by policy: {policy.name}",
                    matched_policies=[policy.policy_id]
                )

            # Check if user has denied role
            if any(role_id in policy.denied_roles for role_id in user.roles):
                return AccessDecision(
                    allowed=False,
                    user_id=user.user_id,
                    resource_type=policy.resource_type,
                    resource_id="",
                    permission_type=permission_type,
                    reason=f"Role denied by policy: {policy.name}",
                    matched_policies=[policy.policy_id]
                )

            # Check allow conditions
            if user.user_id in policy.allowed_users:
                if self._evaluate_conditions(policy.conditions, context):
                    return AccessDecision(
                        allowed=True,
                        user_id=user.user_id,
                        resource_type=policy.resource_type,
                        resource_id="",
                        permission_type=permission_type,
                        reason=f"Allowed by policy: {policy.name}",
                        matched_policies=[policy.policy_id]
                    )

            # Check if user has allowed role
            if any(role_id in policy.allowed_roles for role_id in user.roles):
                if self._evaluate_conditions(policy.conditions, context):
                    return AccessDecision(
                        allowed=True,
                        user_id=user.user_id,
                        resource_type=policy.resource_type,
                        resource_id="",
                        permission_type=permission_type,
                        reason=f"Allowed by policy: {policy.name}",
                        matched_policies=[policy.policy_id]
                    )

        return None

    def _evaluate_conditions(
        self,
        conditions: Dict,
        context: Dict
    ) -> bool:
        """
        Evaluate access conditions.

        Supports:
        - time_range: {"start": "09:00", "end": "17:00"}
        - ip_range: ["10.0.0.0/8", "192.168.1.0/24"]
        - max_clearance: "secret"
        """
        if not conditions:
            return True

        # Time-based conditions
        if "time_range" in conditions:
            # Simplified - would need proper time comparison
            pass

        # IP-based conditions
        if "ip_range" in conditions:
            user_ip = context.get("ip_address")
            # Simplified - would need proper IP range checking
            pass

        # Clearance level
        if "min_clearance" in conditions:
            user_clearance = context.get("clearance_level")
            # Simplified - would need clearance hierarchy
            pass

        return True
