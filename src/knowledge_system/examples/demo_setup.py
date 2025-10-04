#!/usr/bin/env python3
"""
Demo Setup Script for Enterprise Knowledge System

Demonstrates:
1. Setting up multiple knowledge stores
2. Configuring RBAC with roles and permissions
3. Registering workflows
4. Making queries with permission checking
5. Viewing audit logs
"""

import asyncio
import os
from datetime import datetime

# Import knowledge system components
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from knowledge_system.stores.manager import KnowledgeStoreManager
from knowledge_system.stores.base import StoreMetadata, StoreType
from knowledge_system.rbac.service import RBACService
from knowledge_system.rbac.models import Role, User, Permission, PermissionType, AccessPolicy
from knowledge_system.audit.logger import AuditLogger
from knowledge_system.audit.analytics import AuditAnalytics
from knowledge_system.privacy.detector import PIIDetector
from knowledge_system.privacy.obfuscator import DataObfuscator
from knowledge_system.workflows.router import WorkflowRouter
from knowledge_system.workflows.config import WorkflowConfig
from knowledge_system.workflows.models import WorkflowContext


class DemoKnowledgeStore:
    """Simple in-memory knowledge store for demo"""

    def __init__(self, metadata):
        from knowledge_system.stores.base import KnowledgeStore
        self.metadata = metadata
        self._initialized = False
        self.documents = {}

    async def initialize(self):
        self._initialized = True
        return True

    async def health_check(self):
        return {"healthy": self._initialized}

    async def query(self, query_text, user_id, user_roles, max_results=10, filters=None):
        # Simple mock query
        from knowledge_system.stores.base import QueryResult, DocumentMetadata
        return [
            QueryResult(
                doc_id="demo_doc_1",
                store_id=self.metadata.store_id,
                content="This is a demo document about team meetings and collaboration.",
                metadata=DocumentMetadata(
                    doc_id="demo_doc_1",
                    store_id=self.metadata.store_id,
                    title="Demo Document",
                    author="System",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    tags=["demo"],
                    permissions={},
                    sensitivity_level="internal",
                    content_hash="abc123",
                    size_bytes=100,
                    custom_metadata={}
                ),
                similarity_score=0.95,
                chunks=[],
                entities=[],
                obfuscated=False
            )
        ]

    async def get_document(self, doc_id, user_id, user_roles):
        return None

    async def check_permission(self, doc_id, user_id, user_roles, operation="read"):
        return True

    async def index_document(self, doc_id, content, metadata):
        return True

    async def list_documents(self, user_id, user_roles, limit=100, offset=0):
        return []

    async def get_statistics(self):
        return {"document_count": len(self.documents)}


async def setup_demo():
    """Setup demo environment"""
    print("=" * 60)
    print("Enterprise Knowledge System - Demo Setup")
    print("=" * 60)
    print()

    # 1. Initialize Store Manager
    print("1. Initializing Knowledge Store Manager...")
    store_manager = KnowledgeStoreManager()

    # Register demo stores
    stores = [
        ("meetings", StoreType.MEETINGS, "Meeting transcripts and notes"),
        ("emails", StoreType.EMAILS, "Email messages and threads"),
        ("shared_docs", StoreType.SHARED_DOCUMENTS, "Shared documents"),
        ("confidential", StoreType.CONFIDENTIAL, "Confidential data"),
    ]

    for store_id, store_type, description in stores:
        metadata = StoreMetadata(
            store_id=store_id,
            store_type=store_type,
            name=store_id.replace("_", " ").title(),
            description=description,
            enabled=True,
            requires_roles=["employee"],
            pii_level="partial",
            audit_level="detailed",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            connection_config={}
        )
        store = DemoKnowledgeStore(metadata)
        await store.initialize()
        store_manager.register_store(store)
        print(f"   ✓ Registered store: {store_id}")

    print()

    # 2. Setup RBAC
    print("2. Configuring RBAC...")
    rbac = RBACService()

    # Define roles
    roles = [
        Role(
            role_id="employee",
            name="Employee",
            description="Standard employee role",
            permissions=[],
            parent_roles=[]
        ),
        Role(
            role_id="manager",
            name="Manager",
            description="Manager role with elevated access",
            permissions=[],
            parent_roles=["employee"]
        ),
        Role(
            role_id="analyst",
            name="Analyst",
            description="Analyst with confidential data access",
            permissions=[],
            parent_roles=["employee"]
        ),
    ]

    for role in roles:
        rbac.add_role(role)
        print(f"   ✓ Added role: {role.name}")

    # Create demo users
    users = [
        User(
            user_id="alice@company.com",
            email="alice@company.com",
            name="Alice Employee",
            roles=["employee"],
            department="Engineering"
        ),
        User(
            user_id="bob@company.com",
            email="bob@company.com",
            name="Bob Manager",
            roles=["employee", "manager"],
            department="Engineering"
        ),
        User(
            user_id="carol@company.com",
            email="carol@company.com",
            name="Carol Analyst",
            roles=["employee", "analyst"],
            department="Finance"
        ),
    ]

    for user in users:
        rbac.add_user(user)
        print(f"   ✓ Added user: {user.name} ({', '.join(user.roles)})")

    print()

    # 3. Setup Audit Logger
    print("3. Initializing Audit Logger...")
    audit_logger = AuditLogger(
        db_connection_string=os.getenv("DATABASE_URL"),
        log_file_path="/tmp/knowledge_system_audit.log",
        default_audit_level=os.getenv("AUDIT_LEVEL", "detailed")
    )
    # Note: In production, would call await audit_logger.initialize()
    print("   ✓ Audit logger configured")
    print()

    # 4. Setup PII Protection
    print("4. Configuring PII Protection...")
    pii_detector = PIIDetector()
    obfuscator = DataObfuscator(pii_detector)
    print("   ✓ PII detection and obfuscation enabled")
    print()

    # 5. Load Workflows
    print("5. Loading Workflow Configurations...")
    config_path = os.path.join(os.path.dirname(__file__), "workflows.yaml")
    workflow_config = WorkflowConfig(config_path)

    try:
        workflows = workflow_config.load_from_file(config_path)
        print(f"   ✓ Loaded {len(workflows)} workflows")
        for wf in workflows:
            print(f"     - {wf.name}: {', '.join(wf.allowed_stores)}")
    except FileNotFoundError:
        print(f"   ⚠ Workflow config not found at {config_path}")
        print("     Using example configuration...")
        workflows = []

    print()

    # 6. Setup Workflow Router
    print("6. Initializing Workflow Router...")
    router = WorkflowRouter(
        store_manager=store_manager,
        rbac_service=rbac,
        audit_logger=audit_logger,
        obfuscator=obfuscator
    )

    # Register workflows
    for workflow in workflows:
        router.register_workflow(workflow)

    print(f"   ✓ Router initialized with {len(workflows)} workflows")
    print()

    # 7. Demo Queries
    print("7. Running Demo Queries...")
    print()

    # Query as Alice (employee)
    print("   Query 1: Alice (employee) queries meeting_tracker")
    try:
        context = WorkflowContext(
            workflow_id="meeting_tracker",
            user_id="alice@company.com",
            user_email="alice@company.com",
            user_roles=["employee"]
        )

        result = await router.execute_workflow(
            workflow_id="meeting_tracker",
            query="What were the action items from yesterday?",
            context=context
        )

        print(f"   ✓ Success! Found {result.total_results} results")
        print(f"     Answer: {result.answer[:100]}...")
        print()
    except Exception as e:
        print(f"   ✗ Error: {str(e)}")
        print()

    # Query as Carol (analyst) - should have access to confidential
    print("   Query 2: Carol (analyst) queries confidential_research")
    try:
        context = WorkflowContext(
            workflow_id="confidential_research",
            user_id="carol@company.com",
            user_email="carol@company.com",
            user_roles=["employee", "analyst"]
        )

        result = await router.execute_workflow(
            workflow_id="confidential_research",
            query="What is the market outlook?",
            context=context
        )

        print(f"   ✓ Success! Found {result.total_results} results")
        print(f"     Execution time: {result.execution_time_ms:.2f}ms")
        print()
    except Exception as e:
        print(f"   ✗ Error: {str(e)}")
        print()

    # Query as Alice (employee) trying confidential - should fail
    print("   Query 3: Alice (employee) tries confidential_research - should fail")
    try:
        context = WorkflowContext(
            workflow_id="confidential_research",
            user_id="alice@company.com",
            user_email="alice@company.com",
            user_roles=["employee"]
        )

        result = await router.execute_workflow(
            workflow_id="confidential_research",
            query="Market data query",
            context=context
        )

        print(f"   ✗ Unexpected success!")
        print()
    except PermissionError as e:
        print(f"   ✓ Access correctly denied: {str(e)}")
        print()
    except Exception as e:
        print(f"   ✗ Unexpected error: {str(e)}")
        print()

    # 8. Summary
    print("=" * 60)
    print("Demo Setup Complete!")
    print("=" * 60)
    print()
    print("Summary:")
    print(f"  • {len(store_manager.stores)} knowledge stores registered")
    print(f"  • {len(rbac.roles)} roles defined")
    print(f"  • {len(rbac.users)} demo users created")
    print(f"  • {len(workflows)} workflows configured")
    print()
    print("Next steps:")
    print("  1. Review workflow configurations in workflows.yaml")
    print("  2. Integrate with Microsoft services (Power Automate, Copilot Studio)")
    print("  3. Connect MCP servers for real knowledge stores")
    print("  4. Configure audit log retention and compliance reporting")
    print()


if __name__ == "__main__":
    asyncio.run(setup_demo())
