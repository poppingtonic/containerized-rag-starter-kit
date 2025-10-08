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
from knowledge_system.stores.api_management import (
    StoreManagementAPI,
    CreateStoreRequest,
    StoreResponse,
    IndexDocumentRequest,
    StoreHealthResponse
)
from knowledge_system.rbac.service import RBACService
from knowledge_system.rbac.models import Role, User
from knowledge_system.audit.logger import AuditLogger
from knowledge_system.privacy.detector import PIIDetector
from knowledge_system.privacy.obfuscator import DataObfuscator
from knowledge_system.workflows.router import WorkflowRouter
from knowledge_system.workflows.config import WorkflowConfig
from knowledge_system.workflows.models import WorkflowContext
from knowledge_system.ingestion import SmartIngestionService, IngestionResult

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
store_management_api: Optional[StoreManagementAPI] = None
ingestion_service: Optional[SmartIngestionService] = None


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


class IngestFileRequest(BaseModel):
    filepath: str
    metadata: Optional[Dict[str, Any]] = None
    strategy: str = "auto"
    force_store_id: Optional[str] = None


class IngestFileResponse(BaseModel):
    success: bool
    filename: str
    store_id: str
    doc_id: str
    routing_info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time_seconds: Optional[float] = None


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global store_manager, rbac_service, audit_logger, workflow_router, store_management_api, ingestion_service

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

        # Initialize store management API
        openai_api_key = os.getenv("OPENAI_API_KEY")
        store_management_api = StoreManagementAPI(
            store_manager=store_manager,
            db_connection_string=db_url,
            openai_api_key=openai_api_key
        )

        # Initialize smart ingestion service
        unstructured_api_url = os.getenv("UNSTRUCTURED_API_URL", "http://unstructured-api:8000")
        routing_rules_path = os.getenv(
            "ROUTING_RULES_PATH",
            "/app/knowledge_system/examples/routing_rules.yaml"
        )

        # Load store configs from routing rules for auto-creation
        import yaml
        store_configs = {}
        if os.path.exists(routing_rules_path):
            with open(routing_rules_path, 'r') as f:
                config = yaml.safe_load(f)
                store_configs = config.get('store_configs', {})

        ingestion_service = SmartIngestionService(
            unstructured_api_url=unstructured_api_url,
            store_management_api=store_management_api,
            router_config=routing_rules_path,
            auto_create_stores=True,
            store_configs=store_configs
        )
        logger.info("Smart ingestion service initialized")

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
        "store_management_api": store_management_api is not None,
        "ingestion_service": ingestion_service is not None,
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


# Store Management Endpoints

@app.post("/stores", response_model=StoreResponse)
async def create_knowledge_store(request: CreateStoreRequest):
    """
    Create a new knowledge store.

    The store will share the existing PostgreSQL database but partition data by store_id.
    This allows multiple stores to reuse vector search infrastructure while maintaining
    logical separation.
    """
    if not store_management_api:
        raise HTTPException(status_code=503, detail="Store management API not initialized")

    try:
        response = await store_management_api.create_store(request)
        logger.info(f"Created knowledge store: {request.store_id}")
        return response
    except Exception as e:
        logger.error(f"Error creating store: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stores/all", response_model=List[StoreResponse])
async def list_all_stores():
    """List all registered knowledge stores with statistics"""
    if not store_management_api:
        raise HTTPException(status_code=503, detail="Store management API not initialized")

    try:
        stores = await store_management_api.list_stores()
        return stores
    except Exception as e:
        logger.error(f"Error listing stores: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stores/{store_id}", response_model=StoreResponse)
async def get_store_details(store_id: str):
    """Get detailed information about a specific store"""
    if not store_management_api:
        raise HTTPException(status_code=503, detail="Store management API not initialized")

    try:
        store = await store_management_api.get_store(store_id)
        if not store:
            raise HTTPException(status_code=404, detail=f"Store {store_id} not found")
        return store
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting store details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/stores/{store_id}")
async def delete_knowledge_store(store_id: str):
    """
    Remove a knowledge store from the manager.

    Note: This does NOT delete the data from the database.
    Data remains partitioned by store_id and can be re-registered.
    """
    if not store_management_api:
        raise HTTPException(status_code=503, detail="Store management API not initialized")

    try:
        success = await store_management_api.delete_store(store_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Store {store_id} not found")

        return {
            "success": True,
            "store_id": store_id,
            "message": "Store unregistered successfully. Data remains in database."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting store: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stores/{store_id}/health", response_model=StoreHealthResponse)
async def check_store_health(store_id: str):
    """Check health status of a knowledge store"""
    if not store_management_api:
        raise HTTPException(status_code=503, detail="Store management API not initialized")

    try:
        health = await store_management_api.check_store_health(store_id)
        return health
    except Exception as e:
        logger.error(f"Error checking store health: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/stores/{store_id}/documents")
async def index_document_to_store(store_id: str, request: IndexDocumentRequest):
    """
    Index a document into a specific knowledge store.

    The document will be:
    1. Chunked into smaller pieces
    2. Embedded using OpenAI
    3. Stored in the shared database with store_id partition
    4. Indexed for vector similarity search
    """
    if not store_management_api:
        raise HTTPException(status_code=503, detail="Store management API not initialized")

    try:
        result = await store_management_api.index_document(store_id, request)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error indexing document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stores/{store_id}/statistics")
async def get_store_statistics(store_id: str):
    """Get detailed statistics for a knowledge store"""
    if not store_management_api:
        raise HTTPException(status_code=503, detail="Store management API not initialized")

    try:
        stats = await store_management_api.get_store_statistics(store_id)
        return stats
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting store statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Smart Ingestion Endpoints

@app.post("/ingest/file", response_model=IngestFileResponse)
async def ingest_file(request: IngestFileRequest):
    """
    Intelligently ingest a file using unstructured-api.

    The file will be:
    1. Processed by unstructured-api (supports 50+ file types)
    2. Automatically routed to appropriate knowledge store based on type/content
    3. Indexed for vector similarity search

    Supported file types: PDF, Word, PowerPoint, Excel, images, emails, and more
    """
    if not ingestion_service:
        raise HTTPException(status_code=503, detail="Ingestion service not initialized")

    try:
        result = await ingestion_service.ingest_file(
            filepath=request.filepath,
            metadata=request.metadata,
            strategy=request.strategy,
            force_store_id=request.force_store_id
        )

        return IngestFileResponse(
            success=result.success,
            filename=result.filename,
            store_id=result.store_id,
            doc_id=result.doc_id,
            routing_info=result.routing_info,
            error=result.error,
            processing_time_seconds=result.processing_time_seconds
        )

    except Exception as e:
        logger.error(f"Error in ingest_file endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ingest/statistics")
async def get_ingestion_statistics():
    """Get ingestion statistics including routing info"""
    if not ingestion_service:
        raise HTTPException(status_code=503, detail="Ingestion service not initialized")

    try:
        stats = await ingestion_service.get_ingestion_statistics()
        return stats
    except Exception as e:
        logger.error(f"Error getting ingestion statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ingest/routing-rules")
async def get_routing_rules():
    """Get current document routing rules"""
    if not ingestion_service:
        raise HTTPException(status_code=503, detail="Ingestion service not initialized")

    rules = []
    for rule in ingestion_service.router.rules:
        rules.append({
            "rule_id": rule.rule_id,
            "name": rule.name,
            "description": rule.description,
            "strategy": rule.strategy.value,
            "target_store_id": rule.target_store_id,
            "priority": rule.priority,
            "enabled": rule.enabled
        })

    return {"rules": rules}


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Knowledge System Service...")

    if audit_logger:
        await audit_logger.shutdown()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
