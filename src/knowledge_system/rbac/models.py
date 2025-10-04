"""
RBAC data models
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set


class PermissionType(Enum):
    """Types of permissions"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    QUERY = "query"
    INDEX = "index"


@dataclass
class Permission:
    """Represents a permission on a resource"""
    permission_id: str
    resource_type: str  # "store", "document", "workflow"
    resource_id: str
    permission_type: PermissionType
    conditions: Dict[str, any] = field(default_factory=dict)  # Time-based, IP-based, etc.


@dataclass
class Role:
    """Represents a role with permissions"""
    role_id: str
    name: str
    description: str
    permissions: List[Permission] = field(default_factory=list)
    parent_roles: List[str] = field(default_factory=list)  # Role inheritance
    metadata: Dict[str, any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class User:
    """Represents a user in the system"""
    user_id: str
    email: str
    name: str
    roles: List[str] = field(default_factory=list)  # Role IDs
    direct_permissions: List[Permission] = field(default_factory=list)
    department: Optional[str] = None
    clearance_level: Optional[str] = None
    metadata: Dict[str, any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    active: bool = True


@dataclass
class AccessPolicy:
    """Defines an access policy for resources"""
    policy_id: str
    name: str
    description: str
    resource_type: str
    resource_pattern: str  # Glob pattern or regex
    allowed_roles: List[str]
    allowed_users: List[str] = field(default_factory=list)
    denied_roles: List[str] = field(default_factory=list)
    denied_users: List[str] = field(default_factory=list)
    conditions: Dict[str, any] = field(default_factory=dict)
    priority: int = 0  # Higher priority wins
    active: bool = True
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


@dataclass
class AccessDecision:
    """Result of an access control decision"""
    allowed: bool
    user_id: str
    resource_type: str
    resource_id: str
    permission_type: PermissionType
    reason: str
    matched_policies: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class WorkflowPermissionSet:
    """Permission set for a specific workflow"""
    workflow_id: str
    workflow_name: str
    description: str
    allowed_stores: List[str]  # Store IDs that can be accessed
    required_roles: List[str]  # Roles required to use this workflow
    pii_level: str  # PII obfuscation level for this workflow
    audit_level: str  # Audit logging level
    max_results: int = 50
    query_filters: Dict[str, any] = field(default_factory=dict)
    metadata: Dict[str, any] = field(default_factory=dict)
