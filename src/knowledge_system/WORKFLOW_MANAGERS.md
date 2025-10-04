# Workflow Manager Integration Guide

## Overview

The knowledge system now supports **visual workflow management** through:
- **LangGraph Studio**: Graph-based workflows with state management
- **Dify**: Low-code workflow builder with templates

Both integrate seamlessly with the knowledge system's security features (RBAC, audit logging, PII protection).

## Why Visual Workflow Managers?

### Before (YAML-only)
```yaml
workflows:
  meeting_tracker:
    allowed_stores: [meetings]
    required_roles: [employee]
```
- ✅ Simple configuration
- ❌ Limited logic capabilities
- ❌ No visual design
- ❌ Hard to iterate

### After (LangGraph Studio / Dify)
```
[Visual Graph Editor]
Input → Query Store → LLM Analysis → Output
  ↓         ↓              ↓           ↓
State management across all nodes
```
- ✅ Visual design and debugging
- ✅ Complex logic and branching
- ✅ State management
- ✅ Rapid iteration
- ✅ **Still has all security features!**

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  LangGraph Studio / Dify                            │
│  (Visual Workflow Builder)                          │
└──────────────────┬──────────────────────────────────┘
                   │
           ┌───────▼──────────┐
           │ Workflow Manager │  ← API Client
           └───────┬──────────┘
                   │
        ┌──────────▼───────────────┐
        │ Integrated Adapter       │  ← Security Layer
        │ • RBAC Check             │
        │ • Input Sanitization     │
        │ • PII Obfuscation        │
        │ • Audit Logging          │
        │ • Tool Injection         │
        └──────────┬───────────────┘
                   │
      ┌────────────┼────────────┐
      │            │            │
  ┌───▼───┐   ┌───▼───┐   ┌───▼────┐
  │ RBAC  │   │ Audit │   │ Stores │
  └───────┘   └───────┘   └────────┘
```

## Quick Start

### 1. LangGraph Studio Setup

```bash
# Install LangGraph Studio
pip install langgraph-studio

# Start the server
langgraph studio

# Runs on http://localhost:8123
```

**In your Python code:**
```python
from knowledge_system.workflow_managers import LangGraphStudioManager
from knowledge_system.workflow_managers.adapter import IntegratedWorkflowAdapter

# Initialize
langgraph = LangGraphStudioManager(
    api_url="http://localhost:8123",
    api_key="your-api-key"
)
await langgraph.initialize()

# Create adapter with security
adapter = IntegratedWorkflowAdapter(
    workflow_manager=langgraph,
    rbac_service=rbac,
    audit_logger=audit_logger,
    obfuscator=obfuscator,
    store_manager=store_manager
)

# Execute with full security
result = await adapter.execute_workflow_with_security(
    workflow_id="meeting_analyzer",
    inputs={"query": "Summarize meetings"},
    context=context,
    pii_level="partial",
    audit_level="detailed"
)
```

### 2. Dify Setup

```bash
# Sign up at dify.ai
# Create an app in Dify Studio
# Get API key from app settings
```

**In your Python code:**
```python
from knowledge_system.workflow_managers import DifyWorkflowManager

dify = DifyWorkflowManager(
    api_url="https://api.dify.ai/v1",
    api_key="app-your-dify-key"
)
await dify.initialize()

# Use same adapter pattern
adapter = IntegratedWorkflowAdapter(
    workflow_manager=dify,
    # ... same as above
)
```

## Key Features

### Security Integration

The `IntegratedWorkflowAdapter` automatically:

1. **Checks permissions** via RBAC
2. **Sanitizes inputs** to prevent prompt injection
3. **Injects knowledge store tools** into workflow
4. **Obfuscates PII** in outputs
5. **Logs everything** to audit system

### Knowledge System Tools

Workflows can call these tools:

```python
# Available in LangGraph/Dify workflows

# Query stores
results = await query_knowledge_store(
    query="project updates",
    store_ids=["meetings", "emails"],
    max_results=10
)

# Get specific document
doc = await get_document(
    doc_id="doc123",
    store_id="meetings"
)
```

### Workflow Design Patterns

#### Pattern 1: Simple Query
```
Input → Query Store → Format → Output
```

#### Pattern 2: Analysis Pipeline
```
Input → Query Store → Extract → Analyze → Summarize → Output
```

#### Pattern 3: Multi-Store Search
```
Input → [Query Meetings] → Merge → Analyze → Output
        [Query Emails   ] ↗
        [Query Docs     ] ↗
```

#### Pattern 4: Conditional Routing
```
Input → Classify Intent → [Meetings Route]
                         → [Email Route   ]
                         → [Docs Route    ]
```

## Platform Comparison

| Feature | LangGraph Studio | Dify |
|---------|------------------|------|
| **Visual Builder** | ✓ Graph editor | ✓ Flow builder |
| **State Management** | ✓ Built-in checkpoints | ✓ Conversation state |
| **Agent Support** | ✓ Native LangChain | ✓ Via tools |
| **Templates** | ❌ Build from scratch | ✓ Pre-built library |
| **Dataset Management** | ❌ External | ✓ Built-in |
| **Self-hosted** | ✓ Full control | ✓ Cloud or self |
| **Learning Curve** | Medium | Low |
| **Best For** | Complex agents | Quick chatbots |

## Use Cases

### 1. Meeting Analytics (LangGraph Studio)
```
Input: "What were action items from last week?"
  ↓
Query meetings store (last 7 days)
  ↓
Extract action items with LLM
  ↓
Group by assignee
  ↓
Format as table
  ↓
Output: Organized action item list
```

### 2. Email Assistant (Dify)
```
Input: "Find emails about project Alpha"
  ↓
Query emails store (filter: "project Alpha")
  ↓
Summarize with GPT-4
  ↓
Extract key points
  ↓
Output: Email summary with links
```

### 3. Confidential Research (LangGraph)
```
Input: "Market analysis for Q2"
  ↓
Check user has "analyst" role ✓
  ↓
Query confidential store
  ↓
Apply forensic audit logging ✓
  ↓
Analyze trends
  ↓
Obfuscate PII in output ✓
  ↓
Output: Protected market analysis
```

## Migration Path

### From YAML Workflows

**Before:**
```yaml
workflows:
  email_search:
    allowed_stores: [emails]
    required_roles: [employee]
```

**After:**
1. Create workflow in LangGraph Studio/Dify
2. Add nodes for query logic
3. Deploy workflow
4. Use same security adapter
5. All RBAC/audit still works!

### Gradual Migration

You can use both simultaneously:
- Keep simple workflows in YAML
- Move complex workflows to visual builders
- All share same security infrastructure

## Best Practices

### ✅ Do

- Use `IntegratedWorkflowAdapter` in production
- Set appropriate `pii_level` for sensitivity
- Use `audit_level="forensic"` for confidential data
- Test workflows in dev environment first
- Monitor execution times
- Review audit logs regularly

### ❌ Don't

- Don't bypass security adapter
- Don't hardcode credentials in workflows
- Don't skip permission checks
- Don't expose raw database access
- Don't forget to set timeouts

## Security Considerations

### Input Validation

The adapter sanitizes all inputs:
```python
# These patterns are removed:
- "ignore previous instructions"
- "system:"
- "exec()"
- "<|im_start|>"
```

### Permission Boundaries

```python
# Workflow can only access stores user has access to
context = WorkflowContext(
    user_id="alice@company.com",
    user_roles=["employee"]  # Not "analyst"
)

# This will fail:
result = await adapter.execute_workflow_with_security(
    workflow_id="confidential_research",  # Requires "analyst" role
    context=context
)
# Error: "Permission denied: User lacks required roles"
```

### Audit Trail

Every execution is logged:
```python
# Audit log entry:
{
    "event_type": "workflow_executed",
    "user_id": "alice@company.com",
    "workflow_id": "meeting_tracker",
    "execution_id": "exec_123",
    "execution_time_ms": 1234,
    "success": true,
    "stores_accessed": ["meetings"],
    "pii_accessed": false
}
```

## Monitoring

### Check Workflow Health

```python
health = await langgraph.health_check()
if health["healthy"]:
    print("✓ LangGraph Studio operational")
```

### View Execution History

```python
history = await langgraph.get_execution_history(
    workflow_id="meeting_tracker",
    limit=50
)

for execution in history:
    print(f"{execution.timestamp}: {execution.execution_time_ms}ms")
```

### Audit Analytics

```python
from knowledge_system.audit.analytics import AuditAnalytics

analytics = AuditAnalytics(db_url)
stats = await analytics.get_statistics(
    start_time=last_week,
    end_time=now
)

print(f"Total workflow executions: {stats.total_events}")
print(f"Failed executions: {stats.failed_accesses}")
```

## Troubleshooting

### Connection Issues

```
Error: LangGraph Studio not available
```

**Solution:**
1. Check if LangGraph Studio is running: `curl http://localhost:8123/health`
2. Verify API key is correct
3. Check firewall settings

### Permission Denied

```
Error: User lacks required roles: ['analyst']
```

**Solution:**
1. Check user roles in RBAC system
2. Verify workflow requirements match user roles
3. Update user roles or workflow config

### Workflow Timeout

```
Error: Workflow execution timeout
```

**Solution:**
1. Increase timeout: `LangGraphStudioManager(timeout=600)`
2. Optimize workflow (reduce LLM calls)
3. Add progress checkpoints

## Examples

See `examples/workflow_managers_demo.py` for complete examples.

## Documentation

- **API Reference**: See individual files in `workflow_managers/`
- **LangGraph Studio**: https://langchain-ai.github.io/langgraph/
- **Dify**: https://docs.dify.ai/

## Support

For issues:
1. Check logs: `docker-compose logs -f knowledge-system`
2. Review audit logs for execution details
3. Test with simple workflow first
4. Verify all security components initialized

## Summary

With LangGraph Studio and Dify integration:
- ✅ **Visual workflow design** (no code required)
- ✅ **Enterprise security** maintained (RBAC, audit, PII)
- ✅ **Rapid iteration** and debugging
- ✅ **Production ready** with full observability
- ✅ **Backwards compatible** with YAML workflows

Perfect for the Baltare demo! 🎯
