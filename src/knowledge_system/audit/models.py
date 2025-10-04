"""
Audit event models
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class EventType(Enum):
    """Types of auditable events"""
    # Access events
    QUERY = "query"
    DOCUMENT_ACCESS = "document_access"
    STORE_ACCESS = "store_access"

    # Permission events
    PERMISSION_CHECK = "permission_check"
    PERMISSION_DENIED = "permission_denied"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REVOKED = "role_revoked"

    # Data events
    DOCUMENT_INDEXED = "document_indexed"
    DOCUMENT_MODIFIED = "document_modified"
    DOCUMENT_DELETED = "document_deleted"

    # Security events
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    PROMPT_INJECTION_ATTEMPT = "prompt_injection_attempt"

    # System events
    STORE_INITIALIZED = "store_initialized"
    STORE_HEALTH_CHECK = "store_health_check"
    WORKFLOW_EXECUTED = "workflow_executed"


class AuditLevel(Enum):
    """Audit logging levels"""
    BASIC = "basic"  # Essential events only
    DETAILED = "detailed"  # Include context and metadata
    FORENSIC = "forensic"  # Full details for compliance/investigation


@dataclass
class AuditEvent:
    """Represents an auditable event"""
    event_id: str
    event_type: EventType
    timestamp: datetime
    user_id: Optional[str]
    user_email: Optional[str]
    user_roles: list[str] = field(default_factory=list)

    # Resource information
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    store_id: Optional[str] = None

    # Action details
    action: Optional[str] = None
    result: str = "success"  # success, failure, denied
    reason: Optional[str] = None

    # Query information (for query events)
    query_text: Optional[str] = None
    query_results_count: Optional[int] = None

    # Context
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    workflow_id: Optional[str] = None

    # Security flags
    suspicious: bool = False
    pii_accessed: bool = False
    sensitive_data: bool = False

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    audit_level: AuditLevel = AuditLevel.BASIC

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/serialization"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "user_email": self.user_email,
            "user_roles": self.user_roles,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "store_id": self.store_id,
            "action": self.action,
            "result": self.result,
            "reason": self.reason,
            "query_text": self.query_text if self.audit_level != AuditLevel.BASIC else None,
            "query_results_count": self.query_results_count,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "session_id": self.session_id,
            "workflow_id": self.workflow_id,
            "suspicious": self.suspicious,
            "pii_accessed": self.pii_accessed,
            "sensitive_data": self.sensitive_data,
            "metadata": self.metadata,
            "audit_level": self.audit_level.value
        }


@dataclass
class AuditStatistics:
    """Statistics about audit events"""
    total_events: int
    events_by_type: Dict[str, int]
    events_by_user: Dict[str, int]
    events_by_store: Dict[str, int]
    failed_accesses: int
    denied_permissions: int
    suspicious_events: int
    pii_accesses: int
    time_range_start: datetime
    time_range_end: datetime
    top_queries: list[Dict[str, Any]] = field(default_factory=list)
    top_users: list[Dict[str, Any]] = field(default_factory=list)
    security_alerts: list[str] = field(default_factory=list)
