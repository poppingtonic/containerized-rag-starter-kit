# Workflow Managers Integration

Integration layer for external workflow management platforms with the knowledge system's security features.

## Supported Platforms

### 1. **LangGraph Studio**
Visual graph-based workflow builder with:
- Drag-and-drop workflow design
- State management
- Built-in agent nodes
- Checkpointing and recovery
- Real-time debugging

### 2. **Dify**
Low-code workflow platform with:
- Visual workflow builder
- Pre-built templates
- Multi-model LLM support
- Built-in dataset management
- API management

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│          External Workflow Platform                      │
│      (LangGraph Studio / Dify)                          │
└──────────────────┬──────────────────────────────────────┘
                   │
           ┌───────▼──────────┐
           │ Workflow Manager │
           │   (API Client)   │
           └───────┬──────────┘
                   │
        ┌──────────▼───────────────┐
        │ Integrated Adapter       │
        │ - RBAC Check             │
        │ - Input Sanitization     │
        │ - PII Obfuscation        │
        │ - Audit Logging          │
        │ - Tool Injection         │
        └──────────┬───────────────┘
                   │
      ┌────────────┼────────────┐
      │            │            │
  ┌───▼───┐   ┌───▼───┐   ┌───▼────┐
  │ RBAC  │   │ Audit │   │ Stores │
  │Service│   │Logger │   │Manager │
  └───────┘   └───────┘   └────────┘
```

## Quick Start

### LangGraph Studio Setup

```python
from knowledge_system.workflow_managers import LangGraphStudioManager
from knowledge_system.workflow_managers.adapter import IntegratedWorkflowAdapter

# 1. Initialize LangGraph Studio manager
langgraph = LangGraphStudioManager(
    api_url="http://localhost:8123",  # LangGraph Studio URL
    api_key="your-api-key"
)
await langgraph.initialize()

# 2. Create integrated adapter with security features
adapter = IntegratedWorkflowAdapter(
    workflow_manager=langgraph,
    rbac_service=rbac,
    audit_logger=audit_logger,
    obfuscator=obfuscator,
    store_manager=store_manager
)

# 3. Execute workflow with full security
context = WorkflowContext(
    workflow_id="meeting_analyzer",
    user_id="alice@company.com",
    user_email="alice@company.com",
    user_roles=["employee"]
)

result = await adapter.execute_workflow_with_security(
    workflow_id="meeting_analyzer",
    inputs={"query": "Summarize yesterday's meetings"},
    context=context,
    pii_level="partial",
    audit_level="detailed"
)

print(result.output)
```

### Dify Setup

```python
from knowledge_system.workflow_managers import DifyWorkflowManager
from knowledge_system.workflow_managers.adapter import IntegratedWorkflowAdapter

# 1. Initialize Dify manager
dify = DifyWorkflowManager(
    api_url="https://api.dify.ai/v1",
    api_key="app-your-dify-api-key",
    workspace_id="optional-workspace-id"
)
await dify.initialize()

# 2. Create integrated adapter
adapter = IntegratedWorkflowAdapter(
    workflow_manager=dify,
    rbac_service=rbac,
    audit_logger=audit_logger,
    obfuscator=obfuscator,
    store_manager=store_manager
)

# 3. Execute workflow
result = await adapter.execute_workflow_with_security(
    workflow_id="email_assistant",
    inputs={
        "query": "Find emails about project Alpha",
        "date_range": "last_week"
    },
    context=context,
    pii_level="metadata_only"
)
```

## Features

### Security Integration

The adapter automatically applies:

1. **RBAC Permission Checks**
   - Validates user has access to workflow
   - Checks role requirements
   - Denies unauthorized access

2. **Input Sanitization**
   - Prevents prompt injection attacks
   - Removes dangerous patterns
   - Limits input length

3. **PII Obfuscation**
   - Applies to workflow outputs
   - Configurable sensitivity levels
   - Preserves text structure

4. **Audit Logging**
   - Logs all workflow executions
   - Captures success/failure
   - Records execution time
   - Stores user context

5. **Knowledge Store Access**
   - Injects tools into workflows
   - Enforces store permissions
   - Provides secure document access

### Knowledge System Tools

Workflows can call these tools:

```python
# Available in LangGraph/Dify workflows

# Query knowledge stores
results = await query_knowledge_store(
    query="project status",
    store_ids=["meetings", "emails"],
    max_results=10
)

# Get specific document
doc = await get_document(
    doc_id="doc123",
    store_id="meetings"
)
```

## LangGraph Studio Workflows

### Creating a Workflow in LangGraph Studio

1. Open LangGraph Studio UI
2. Create new graph
3. Add nodes:
   - **Input Node**: Receives user query
   - **Query Node**: Calls `query_knowledge_store` tool
   - **Analysis Node**: Processes results with LLM
   - **Output Node**: Returns formatted response

4. Configure state:
```python
{
    "query": str,
    "results": List[Dict],
    "answer": str
}
```

5. Save and deploy

### Example Graph Definition

```json
{
  "nodes": [
    {
      "id": "input",
      "type": "input",
      "data": {"variable": "query"}
    },
    {
      "id": "query_store",
      "type": "tool",
      "data": {
        "tool_name": "query_knowledge_store",
        "inputs": {
          "query": "{{query}}",
          "max_results": 5
        }
      }
    },
    {
      "id": "analyze",
      "type": "llm",
      "data": {
        "model": "gpt-4",
        "prompt": "Analyze these results: {{results}}"
      }
    },
    {
      "id": "output",
      "type": "output",
      "data": {"variable": "answer"}
    }
  ],
  "edges": [
    {"from": "input", "to": "query_store"},
    {"from": "query_store", "to": "analyze"},
    {"from": "analyze", "to": "output"}
  ]
}
```

## Dify Workflows

### Creating a Workflow in Dify

1. Open Dify Studio
2. Create new App (Workflow type)
3. Add blocks:
   - **Start Block**: Define input variables
   - **HTTP Request**: Call knowledge system API
   - **LLM Block**: Process with AI
   - **End Block**: Output results

4. Configure variables:
```yaml
inputs:
  - name: query
    type: text
    required: true
  - name: store_ids
    type: array
    required: false
```

5. Publish workflow

### Example Dify DSL

```yaml
version: "1.0"
name: "Knowledge Query Workflow"
description: "Query knowledge stores with AI analysis"

nodes:
  - id: start
    type: start
    inputs:
      - query: string
      - max_results: number

  - id: query_api
    type: http-request
    config:
      method: POST
      url: "http://api/query"
      body:
        query: "{{start.query}}"
        max_results: "{{start.max_results}}"

  - id: analyze
    type: llm
    config:
      model: gpt-4
      prompt: |
        Analyze these search results and provide a summary:
        {{query_api.response}}

  - id: end
    type: end
    outputs:
      - answer: "{{analyze.output}}"
```

## Advanced Usage

### Custom Workflow Manager

Implement custom workflow platform:

```python
from knowledge_system.workflow_managers.base import WorkflowManager

class CustomWorkflowManager(WorkflowManager):
    def __init__(self, config):
        super().__init__("custom_platform")
        self.config = config

    async def initialize(self):
        # Connect to your platform
        pass

    async def execute_workflow(self, workflow_id, inputs, user_context):
        # Execute workflow
        pass

    # Implement other abstract methods...
```

### Multi-Platform Support

Use multiple workflow managers:

```python
# Initialize both platforms
langgraph_adapter = IntegratedWorkflowAdapter(langgraph, ...)
dify_adapter = IntegratedWorkflowAdapter(dify, ...)

# Route based on workflow platform
workflow = await get_workflow(workflow_id)

if workflow.platform == "langgraph_studio":
    result = await langgraph_adapter.execute_workflow_with_security(...)
elif workflow.platform == "dify":
    result = await dify_adapter.execute_workflow_with_security(...)
```

### Workflow Versioning

```python
# Deploy new version
new_workflow = WorkflowDefinition(
    workflow_id="meeting_analyzer",
    name="Meeting Analyzer",
    version="2.0",
    graph_definition={...}
)

await langgraph.deploy_workflow(new_workflow)

# Get execution history
history = await langgraph.get_execution_history(
    workflow_id="meeting_analyzer",
    limit=50
)
```

## Configuration

### Environment Variables

```bash
# LangGraph Studio
LANGGRAPH_API_URL=http://localhost:8123
LANGGRAPH_API_KEY=your-api-key

# Dify
DIFY_API_URL=https://api.dify.ai/v1
DIFY_API_KEY=app-your-api-key
DIFY_WORKSPACE_ID=workspace-id

# Security
WORKFLOW_TIMEOUT=300
ENABLE_INPUT_SANITIZATION=true
DEFAULT_PII_LEVEL=partial
DEFAULT_AUDIT_LEVEL=detailed
```

### Docker Compose

```yaml
services:
  langgraph-studio:
    image: langgraph/studio:latest
    ports:
      - "8123:8123"
    environment:
      - LANGCHAIN_API_KEY=${LANGCHAIN_API_KEY}

  knowledge-system:
    build: .
    environment:
      - LANGGRAPH_API_URL=http://langgraph-studio:8123
      - DIFY_API_URL=${DIFY_API_URL}
    depends_on:
      - langgraph-studio
```

## Best Practices

### 1. Security

- ✅ Always use `IntegratedWorkflowAdapter` for production
- ✅ Set appropriate `pii_level` based on data sensitivity
- ✅ Use `audit_level="forensic"` for confidential workflows
- ✅ Validate user permissions before workflow execution

### 2. Performance

- ✅ Use workflow caching when possible
- ✅ Set reasonable timeouts
- ✅ Limit `max_results` in queries
- ✅ Use streaming for long-running workflows

### 3. Error Handling

```python
try:
    result = await adapter.execute_workflow_with_security(...)
    if not result.success:
        logger.error(f"Workflow failed: {result.error}")
        # Handle failure
except Exception as e:
    logger.exception("Workflow execution error")
    # Fallback logic
```

### 4. Monitoring

```python
# Track execution time
logger.info(f"Workflow completed in {result.execution_time_ms}ms")

# Monitor step execution
for step in result.steps_executed:
    logger.debug(f"Step: {step}")

# Check audit logs
stats = await audit_analytics.get_statistics(
    start_time=yesterday,
    end_time=now
)
```

## Troubleshooting

### Connection Issues

```python
# Test connection
health = await langgraph.health_check()
if not health["healthy"]:
    logger.error(f"LangGraph unhealthy: {health.get('error')}")
```

### Permission Errors

```python
# Check user access
workflows = await adapter.list_accessible_workflows(
    user_roles=["employee"]
)
# Verify workflow is in list
```

### Workflow Failures

```python
# Get execution history
history = await langgraph.get_execution_history(workflow_id)
for execution in history:
    if not execution.success:
        logger.error(f"Failed execution: {execution.error}")
```

## API Reference

See individual files for detailed API:
- `base.py` - Abstract base classes
- `langgraph_studio.py` - LangGraph Studio implementation
- `dify.py` - Dify implementation
- `adapter.py` - Security integration adapter

## Examples

See `examples/workflow_managers_demo.py` for complete examples.
