"""
RBAC (Role-Based Access Control) System

Provides permission gating for knowledge stores with:
- Role management
- Permission checking
- Integration with identity providers
- Workflow-based access control
"""

from .models import Role, Permission, User, AccessPolicy
from .service import RBACService
from .providers import IdentityProvider, AzureADProvider

__all__ = [
    "Role",
    "Permission",
    "User",
    "AccessPolicy",
    "RBACService",
    "IdentityProvider",
    "AzureADProvider",
]
