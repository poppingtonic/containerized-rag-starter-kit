"""
Knowledge System Service

Main FastAPI application that integrates the knowledge system
with existing Consilience services.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import knowledge system components
import sys
sys.path.insert(0, '/app')

from knowledge_system.stores.manager import KnowledgeStoreManager
from knowledge_system.stores.base import StoreMetadata, StoreType
from knowledge_system.rbac.service import RBACService
from knowledge_system.rbac.models import Role, User
from knowledge_system.audit.logger import AuditLogger
from knowledge_system.privacy.detector import PIIDetector
from knowledge_system.privacy.obfuscator import DataObfuscator
from knowledge_system.workflows.router import WorkflowRouter
from knowledge_system.workflows.config import WorkflowConfig
from knowledge_system.workflows.models import WorkflowContext

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Knowledge System Service",
    description="Enterprise knowledge management with RBAC, audit, and PII protection",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
store_manager: Optional[KnowledgeStoreManager] = None
rbac_service: Optional[RBACService] = None
audit_logger: Optional[AuditLogger] = None
workflow_router: Optional[WorkflowRouter] = None


# Request/Response Models
class QueryRequest(BaseModel):
    query: str
    workflow_id: str
    user_id: str
    user_email: str
    user_roles: List[str]
    max_results: Optional[int] = 50
    filters: Optional[Dict[str, Any]] = None


class QueryResponse(BaseModel):
    success: bool
    workflow_id: str
    query: str
    answer: str
    stores_queried: List[str]
    total_results: int
    execution_time_ms: float
    obfuscated: bool
    error: Optional[str] = None


class WorkflowInfo(BaseModel):
    workflow_id: str
    name: str
    description: str
    allowed_stores: List[str]
    required_roles: List[str]
    pii_level: str


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    components: Dict[str, bool]


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global store_manager, rbac_service, audit_logger, workflow_router

    logger.info("Starting Knowledge System Service...")

    try:
        # Initialize components
        store_manager = KnowledgeStoreManager()
        rbac_service = RBACService()

        # Initialize audit logger
        db_url = os.getenv("DATABASE_URL")
        audit_logger = AuditLogger(
            db_connection_string=db_url,
            log_file_path="/app/logs/audit.log"
        )
        await audit_logger.initialize()

        # Initialize privacy components
        pii_detector = PIIDetector()
        obfuscator = DataObfuscator(pii_detector)

        # Initialize workflow router
        workflow_router = WorkflowRouter(
            store_manager=store_manager,
            rbac_service=rbac_service,
            audit_logger=audit_logger,
            obfuscator=obfuscator
        )

        # Load workflows
        workflow_config_path = os.getenv(
            "WORKFLOW_CONFIG_PATH",
            "/app/knowledge_system/examples/workflows.yaml"
        )
        if os.path.exists(workflow_config_path):
            config = WorkflowConfig(workflow_config_path)
            workflows = config.load_from_file(workflow_config_path)
            for workflow in workflows:
                workflow_router.register_workflow(workflow)
            logger.info(f"Loaded {len(workflows)} workflows")

        # Setup demo RBAC roles
        _setup_demo_rbac()

        logger.info("Knowledge System Service initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize service: {str(e)}")
        raise


def _setup_demo_rbac():
    """Setup demo roles and users"""
    # Define roles
    roles = [
        Role(role_id="employee", name="Employee", description="Standard employee", permissions=[], parent_roles=[]),
        Role(role_id="manager", name="Manager", description="Manager role", permissions=[], parent_roles=["employee"]),
        Role(role_id="analyst", name="Analyst", description="Analyst role", permissions=[], parent_roles=["employee"]),
        Role(role_id="demo_user", name="Demo User", description="Demo role", permissions=[], parent_roles=["employee"]),
    ]

    for role in roles:
        rbac_service.add_role(role)

    # Create demo users
    users = [
        User(user_id="demo@company.com", email="demo@company.com", name="Demo User",
             roles=["employee", "demo_user"], department="Demo"),
        User(user_id="alice@company.com", email="alice@company.com", name="Alice Employee",
             roles=["employee"], department="Engineering"),
        User(user_id="bob@company.com", email="bob@company.com", name="Bob Manager",
             roles=["employee", "manager"], department="Engineering"),
    ]

    for user in users:
        rbac_service.add_user(user)


@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint"""
    return {
        "service": "Knowledge System Service",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    components = {
        "store_manager": store_manager is not None,
        "rbac_service": rbac_service is not None,
        "audit_logger": audit_logger is not None and audit_logger._initialized,
        "workflow_router": workflow_router is not None,
    }

    all_healthy = all(components.values())

    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        timestamp=datetime.utcnow().isoformat(),
        components=components
    )


@app.get("/workflows", response_model=List[WorkflowInfo])
async def list_workflows(
    user_roles: Optional[str] = Header(None, alias="X-User-Roles")
):
    """List available workflows"""
    if not workflow_router:
        raise HTTPException(status_code=503, detail="Workflow router not initialized")

    # Parse user roles
    roles = user_roles.split(",") if user_roles else ["employee"]

    # Get accessible workflows
    accessible = workflow_router.get_accessible_workflows(roles)

    return [
        WorkflowInfo(
            workflow_id=wf.workflow_id,
            name=wf.name,
            description=wf.description,
            allowed_stores=wf.allowed_stores,
            required_roles=wf.required_roles,
            pii_level=wf.pii_level
        )
        for wf in accessible
    ]


@app.post("/query", response_model=QueryResponse)
async def execute_query(request: QueryRequest):
    """Execute a workflow query"""
    if not workflow_router:
        raise HTTPException(status_code=503, detail="Workflow router not initialized")

    try:
        # Create workflow context
        context = WorkflowContext(
            workflow_id=request.workflow_id,
            user_id=request.user_id,
            user_email=request.user_email,
            user_roles=request.user_roles
        )

        # Execute workflow
        result = await workflow_router.execute_workflow(
            workflow_id=request.workflow_id,
            query=request.query,
            context=context
        )

        return QueryResponse(
            success=True,
            workflow_id=request.workflow_id,
            query=request.query,
            answer=result.answer,
            stores_queried=result.stores_queried,
            total_results=result.total_results,
            execution_time_ms=result.execution_time_ms,
            obfuscated=result.obfuscated
        )

    except PermissionError as e:
        return QueryResponse(
            success=False,
            workflow_id=request.workflow_id,
            query=request.query,
            answer="",
            stores_queried=[],
            total_results=0,
            execution_time_ms=0,
            obfuscated=False,
            error=f"Permission denied: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        return QueryResponse(
            success=False,
            workflow_id=request.workflow_id,
            query=request.query,
            answer="",
            stores_queried=[],
            total_results=0,
            execution_time_ms=0,
            obfuscated=False,
            error=str(e)
        )


@app.get("/stores")
async def list_stores(
    user_roles: Optional[str] = Header(None, alias="X-User-Roles")
):
    """List accessible knowledge stores"""
    if not store_manager:
        raise HTTPException(status_code=503, detail="Store manager not initialized")

    roles = user_roles.split(",") if user_roles else ["employee"]
    accessible = store_manager.get_accessible_stores(roles)

    return {
        "stores": [
            {
                "store_id": store.store_id,
                "name": store.name,
                "type": store.store_type.value,
                "description": store.description,
                "requires_roles": store.requires_roles
            }
            for store in accessible
        ]
    }


@app.get("/audit/statistics")
async def get_audit_statistics(
    days: int = 7
):
    """Get audit statistics"""
    from datetime import timedelta
    from knowledge_system.audit.analytics import AuditAnalytics

    try:
        db_url = os.getenv("DATABASE_URL")
        analytics = AuditAnalytics(db_url)

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)

        stats = await analytics.get_statistics(start_time, end_time)

        return {
            "total_events": stats.total_events,
            "events_by_type": stats.events_by_type,
            "failed_accesses": stats.failed_accesses,
            "denied_permissions": stats.denied_permissions,
            "suspicious_events": stats.suspicious_events,
            "pii_accesses": stats.pii_accesses,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error getting audit statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Knowledge System Service...")

    if audit_logger:
        await audit_logger.shutdown()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
