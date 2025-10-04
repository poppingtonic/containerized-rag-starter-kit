#!/usr/bin/env python3
"""
Workflow Managers Demo

Demonstrates integration of LangGraph Studio and Dify with
the knowledge system's security features.
"""

import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from knowledge_system.workflow_managers import (
    LangGraphStudioManager,
    DifyWorkflowManager,
)
from knowledge_system.workflow_managers.adapter import IntegratedWorkflowAdapter
from knowledge_system.workflows.models import WorkflowContext


async def demo_langgraph_studio():
    """Demonstrate LangGraph Studio integration"""
    print("=" * 60)
    print("LangGraph Studio Integration Demo")
    print("=" * 60)
    print()

    # Initialize LangGraph Studio manager
    print("1. Initializing LangGraph Studio connection...")
    langgraph = LangGraphStudioManager(
        api_url=os.getenv("LANGGRAPH_API_URL", "http://localhost:8123"),
        api_key=os.getenv("LANGGRAPH_API_KEY")
    )

    # Check if LangGraph Studio is running
    health = await langgraph.health_check()
    if not health.get("healthy"):
        print(f"   ⚠ LangGraph Studio not available: {health.get('error')}")
        print("   To run this demo:")
        print("   1. Install LangGraph Studio: pip install langgraph-studio")
        print("   2. Start server: langgraph studio")
        print("   3. Export API URL: export LANGGRAPH_API_URL=http://localhost:8123")
        print()
        return

    init_success = await langgraph.initialize()
    if init_success:
        print("   ✓ Connected to LangGraph Studio")
    else:
        print("   ✗ Failed to initialize")
        return

    print()

    # List available workflows
    print("2. Listing available workflows...")
    workflows = await langgraph.list_workflows()
    print(f"   Found {len(workflows)} workflows:")
    for wf in workflows:
        print(f"   - {wf.name} (v{wf.version})")
        print(f"     ID: {wf.workflow_id}")
        print(f"     Tools: {', '.join(wf.tools)}")
    print()

    if not workflows:
        print("   No workflows found. Create one in LangGraph Studio UI.")
        print()
        return

    # Execute a workflow
    print("3. Executing workflow...")
    workflow_id = workflows[0].workflow_id

    context = WorkflowContext(
        workflow_id=workflow_id,
        user_id="demo@company.com",
        user_email="demo@company.com",
        user_roles=["employee", "demo_user"]
    )

    # Note: In production, would use IntegratedWorkflowAdapter
    # Here we show direct execution for simplicity
    result = await langgraph.execute_workflow(
        workflow_id=workflow_id,
        inputs={"query": "What are the latest updates?"},
        user_context=context.to_dict()
    )

    if result.success:
        print(f"   ✓ Execution successful (ID: {result.execution_id})")
        print(f"   Execution time: {result.execution_time_ms:.2f}ms")
        print(f"   Steps executed: {len(result.steps_executed)}")
        print(f"   Output: {result.output}")
    else:
        print(f"   ✗ Execution failed: {result.error}")

    print()

    # Get execution history
    print("4. Retrieving execution history...")
    history = await langgraph.get_execution_history(workflow_id, limit=5)
    print(f"   Found {len(history)} recent executions:")
    for i, exec_result in enumerate(history[:3], 1):
        status = "✓" if exec_result.success else "✗"
        print(f"   {i}. {status} {exec_result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"      Time: {exec_result.execution_time_ms:.0f}ms")

    print()
    await langgraph.shutdown()


async def demo_dify():
    """Demonstrate Dify integration"""
    print("=" * 60)
    print("Dify Integration Demo")
    print("=" * 60)
    print()

    # Initialize Dify manager
    print("1. Initializing Dify connection...")
    dify = DifyWorkflowManager(
        api_url=os.getenv("DIFY_API_URL", "https://api.dify.ai/v1"),
        api_key=os.getenv("DIFY_API_KEY", "app-demo-key"),
        workspace_id=os.getenv("DIFY_WORKSPACE_ID")
    )

    health = await dify.health_check()
    if not health.get("healthy"):
        print(f"   ⚠ Dify not available: {health.get('error')}")
        print("   To run this demo:")
        print("   1. Sign up at dify.ai")
        print("   2. Create an app")
        print("   3. Export API key: export DIFY_API_KEY=app-your-key")
        print()
        return

    init_success = await dify.initialize()
    if init_success:
        print("   ✓ Connected to Dify")
    else:
        print("   ✗ Failed to initialize")
        return

    print()

    # List available workflows (apps)
    print("2. Listing available apps...")
    workflows = await dify.list_workflows()
    print(f"   Found {len(workflows)} apps:")
    for wf in workflows:
        print(f"   - {wf.name}")
        print(f"     Mode: {wf.metadata.get('mode', 'unknown')}")
        print(f"     Variables: {', '.join(wf.variables.keys())}")
    print()

    if not workflows:
        print("   No apps found. Create one in Dify Studio.")
        print()
        return

    # Execute a workflow
    print("3. Executing workflow...")
    workflow_id = workflows[0].workflow_id

    context = WorkflowContext(
        workflow_id=workflow_id,
        user_id="demo@company.com",
        user_email="demo@company.com",
        user_roles=["employee"]
    )

    result = await dify.execute_workflow(
        workflow_id=workflow_id,
        inputs={"query": "Hello, can you help me?"},
        user_context=context.to_dict()
    )

    if result.success:
        print(f"   ✓ Execution successful")
        print(f"   Execution time: {result.execution_time_ms:.2f}ms")
        print(f"   Output: {result.output}")
        if "tokens_used" in result.metadata:
            tokens = result.metadata["tokens_used"]
            print(f"   Tokens used: {tokens}")
    else:
        print(f"   ✗ Execution failed: {result.error}")

    print()
    await dify.shutdown()


async def demo_integrated_adapter():
    """Demonstrate integrated adapter with full security"""
    print("=" * 60)
    print("Integrated Workflow Adapter Demo")
    print("=" * 60)
    print()

    print("This demonstrates how workflows integrate with:")
    print("  • RBAC permission checking")
    print("  • Input sanitization")
    print("  • PII obfuscation")
    print("  • Audit logging")
    print("  • Knowledge store access")
    print()

    print("Example usage:")
    print()
    print("```python")
    print("# Initialize all components")
    print("rbac = RBACService()")
    print("audit_logger = AuditLogger(db_url)")
    print("obfuscator = DataObfuscator()")
    print("store_manager = KnowledgeStoreManager()")
    print("langgraph = LangGraphStudioManager(api_url)")
    print()
    print("# Create integrated adapter")
    print("adapter = IntegratedWorkflowAdapter(")
    print("    workflow_manager=langgraph,")
    print("    rbac_service=rbac,")
    print("    audit_logger=audit_logger,")
    print("    obfuscator=obfuscator,")
    print("    store_manager=store_manager")
    print(")")
    print()
    print("# Execute with full security")
    print("context = WorkflowContext(")
    print("    workflow_id='meeting_analyzer',")
    print("    user_id='alice@company.com',")
    print("    user_roles=['employee']")
    print(")")
    print()
    print("result = await adapter.execute_workflow_with_security(")
    print("    workflow_id='meeting_analyzer',")
    print("    inputs={'query': 'Summarize meetings'},")
    print("    context=context,")
    print("    pii_level='partial',")
    print("    audit_level='detailed'")
    print(")")
    print("```")
    print()

    print("Security features applied:")
    print("  1. ✓ Permission check (RBAC)")
    print("  2. ✓ Input sanitization (prevent injection)")
    print("  3. ✓ Tool injection (knowledge store access)")
    print("  4. ✓ Workflow execution")
    print("  5. ✓ PII obfuscation (output protection)")
    print("  6. ✓ Audit logging (compliance)")
    print()


async def demo_workflow_comparison():
    """Compare LangGraph Studio and Dify"""
    print("=" * 60)
    print("LangGraph Studio vs Dify Comparison")
    print("=" * 60)
    print()

    print("┌────────────────────────┬─────────────────────┬──────────────────┐")
    print("│ Feature                │ LangGraph Studio    │ Dify             │")
    print("├────────────────────────┼─────────────────────┼──────────────────┤")
    print("│ Visual Builder         │ ✓ Graph-based       │ ✓ Flow-based     │")
    print("│ State Management       │ ✓ Built-in          │ ✓ Conversation   │")
    print("│ Agent Support          │ ✓ Native            │ ✓ Via tools      │")
    print("│ Checkpointing          │ ✓ Automatic         │ ✗ Manual         │")
    print("│ LLM Flexibility        │ ✓ Any provider      │ ✓ Multiple       │")
    print("│ Template Library       │ ✗ Build from scratch│ ✓ Pre-built      │")
    print("│ Dataset Management     │ ✗ External          │ ✓ Built-in       │")
    print("│ Self-hosted            │ ✓ Full control      │ ✓ Cloud/Self     │")
    print("│ API Management         │ ✓ Custom            │ ✓ Built-in       │")
    print("│ Learning Curve         │ Medium              │ Low              │")
    print("└────────────────────────┴─────────────────────┴──────────────────┘")
    print()

    print("Recommendation:")
    print("  • Use LangGraph Studio for: Complex agent workflows, custom logic")
    print("  • Use Dify for: Quick prototypes, standard chatbots")
    print("  • Both integrate seamlessly with knowledge system security!")
    print()


async def main():
    """Run all demos"""
    print("\n")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  Enterprise Knowledge System                             ║")
    print("║  Workflow Managers Demo                                  ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    # Run demos
    await demo_workflow_comparison()
    await demo_integrated_adapter()

    # Try LangGraph Studio
    try:
        await demo_langgraph_studio()
    except Exception as e:
        print(f"LangGraph Studio demo skipped: {str(e)}\n")

    # Try Dify
    try:
        await demo_dify()
    except Exception as e:
        print(f"Dify demo skipped: {str(e)}\n")

    print("=" * 60)
    print("Demo Complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Set up LangGraph Studio or Dify")
    print("  2. Create workflows in the visual builder")
    print("  3. Use IntegratedWorkflowAdapter for production")
    print("  4. Configure RBAC, audit, and PII protection")
    print("  5. Monitor execution via audit logs")
    print()


if __name__ == "__main__":
    asyncio.run(main())
