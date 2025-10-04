"""
Workflow models
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Workflow:
    """
    Defines a workflow with specific knowledge store access.

    Examples:
    - "meeting_tracker": Only access meeting notes
    - "project_assistant": Access project docs and shared files
    - "confidential_research": Access confidential store with strict audit
    """
    workflow_id: str
    name: str
    description: str

    # Access control
    allowed_stores: List[str]  # Store IDs
    required_roles: List[str]  # Roles required
    denied_roles: List[str] = field(default_factory=list)

    # Privacy settings
    pii_level: str = "partial"  # full, partial, metadata_only
    obfuscation_enabled: bool = True

    # Audit settings
    audit_level: str = "detailed"  # basic, detailed, forensic
    log_queries: bool = True
    log_results: bool = False

    # Query settings
    max_results: int = 50
    default_filters: Dict[str, Any] = field(default_factory=dict)
    enable_amplification: bool = False
    enable_smart_selection: bool = True

    # Integration settings
    integration_type: Optional[str] = None  # power_automate, copilot_studio, etc.
    integration_config: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowContext:
    """
    Context for a workflow execution.

    Includes user information, session details, and request metadata.
    """
    workflow_id: str
    user_id: str
    user_email: str
    user_roles: List[str]

    # Session information
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Network information
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    # Additional context
    department: Optional[str] = None
    clearance_level: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "workflow_id": self.workflow_id,
            "user_id": self.user_id,
            "user_email": self.user_email,
            "user_roles": self.user_roles,
            "session_id": self.session_id,
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "department": self.department,
            "clearance_level": self.clearance_level,
            "metadata": self.metadata
        }


@dataclass
class WorkflowQueryResult:
    """Result from a workflow query"""
    workflow_id: str
    query: str
    answer: str
    stores_queried: List[str]
    total_results: int
    results: List[Dict[str, Any]]
    entities: List[Dict[str, Any]] = field(default_factory=list)
    obfuscated: bool = False
    audit_logged: bool = True
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
