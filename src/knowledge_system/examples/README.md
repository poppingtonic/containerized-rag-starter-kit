# Enterprise Knowledge System - Examples

This directory contains example configurations and demo scripts for the Enterprise Knowledge System.

## Files

- **`workflows.yaml`**: Example workflow configurations showing different use cases
- **`demo_setup.py`**: Demo script that sets up the system and runs example queries
- **`requirements.txt`**: Python dependencies for running examples

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/dbname"
export OPENAI_API_KEY="your-api-key"
export AUDIT_LEVEL="detailed"
```

### 3. Run Demo

```bash
python demo_setup.py
```

## Example Workflows

### Meeting Tracker
- **Purpose**: Track meeting notes and action items
- **Access**: All employees
- **Stores**: Meetings only
- **Privacy**: Metadata only (high obfuscation)
- **Use Case**: "What were the action items from yesterday's standup?"

### Project Assistant
- **Purpose**: Access project-specific documents
- **Access**: Project members
- **Stores**: Project teams, shared documents
- **Privacy**: Partial obfuscation
- **Use Case**: "Show me the latest sprint planning documents"

### Confidential Research
- **Purpose**: Access market data and research
- **Access**: Analysts and managers only
- **Stores**: Confidential data only
- **Privacy**: Full access, no obfuscation
- **Audit**: Forensic level (all queries and results logged)
- **Use Case**: "What is the market outlook for Q2?"

### Email Search
- **Purpose**: Search email messages
- **Access**: All employees
- **Stores**: Emails
- **Privacy**: Partial obfuscation
- **Integration**: Power Automate connector
- **Use Case**: "Find emails about project Alpha from last month"

## Testing Different Scenarios

### Scenario 1: Basic Employee Access

```python
# Alice (employee) queries meetings
context = WorkflowContext(
    workflow_id="meeting_tracker",
    user_id="alice@company.com",
    user_roles=["employee"]
)

result = await router.execute_workflow(
    workflow_id="meeting_tracker",
    query="Show recent meeting notes",
    context=context
)
```

### Scenario 2: Manager with Elevated Access

```python
# Bob (manager) accesses multiple stores
context = WorkflowContext(
    workflow_id="project_assistant",
    user_id="bob@company.com",
    user_roles=["employee", "manager"]
)

result = await router.execute_workflow(
    workflow_id="project_assistant",
    query="Project status update",
    context=context
)
```

### Scenario 3: Confidential Data Access

```python
# Carol (analyst) queries confidential data
context = WorkflowContext(
    workflow_id="confidential_research",
    user_id="carol@company.com",
    user_roles=["employee", "analyst"]
)

result = await router.execute_workflow(
    workflow_id="confidential_research",
    query="Market analysis",
    context=context
)
```

### Scenario 4: Access Denied

```python
# Alice (employee) tries to access confidential data
# This should fail with PermissionError
context = WorkflowContext(
    workflow_id="confidential_research",
    user_id="alice@company.com",
    user_roles=["employee"]  # Missing "analyst" role
)

# Raises: PermissionError: Access denied
result = await router.execute_workflow(
    workflow_id="confidential_research",
    query="Confidential query",
    context=context
)
```

## Customizing Workflows

Edit `workflows.yaml` to add new workflows:

```yaml
workflows:
  my_workflow:
    name: "My Custom Workflow"
    description: "Description here"

    allowed_stores:
      - store1
      - store2

    required_roles:
      - role1

    pii_level: partial
    audit_level: detailed
    max_results: 50

    active: true
```

## Integration Examples

### Power Automate

The system provides a REST API compatible with Power Automate:

```bash
curl -X POST http://localhost:8000/power-automate/query \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Your question",
    "workflow_id": "meeting_tracker",
    "user_email": "user@company.com"
  }'
```

### Copilot Studio

Send conversational messages:

```bash
curl -X POST http://localhost:8000/copilot-studio/message \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "What were yesterday action items?",
    "user_id": "user@company.com",
    "conversation_id": "conv-123",
    "workflow_id": "meeting_tracker"
  }'
```

## Audit Log Analysis

After running queries, check the audit logs:

```python
from knowledge_system.audit.analytics import AuditAnalytics
from datetime import datetime, timedelta

analytics = AuditAnalytics(db_connection_string)

# Get statistics for last 24 hours
stats = await analytics.get_statistics(
    start_time=datetime.utcnow() - timedelta(days=1),
    end_time=datetime.utcnow()
)

print(f"Total events: {stats.total_events}")
print(f"Failed accesses: {stats.failed_accesses}")
print(f"PII accesses: {stats.pii_accesses}")
```

## Security Features Demo

### PII Detection

```python
from knowledge_system.privacy.detector import PIIDetector

detector = PIIDetector()
text = "Contact John at john.doe@company.com or (555) 123-4567"

entities = detector.detect(text)
for entity in entities:
    print(f"Found {entity.pii_type.value}: {entity.text}")
```

### Data Obfuscation

```python
from knowledge_system.privacy.obfuscator import DataObfuscator
from knowledge_system.privacy.models import SensitivityLevel

obfuscator = DataObfuscator()
text = "Email john.doe@company.com for access"

# Partial obfuscation
obfuscated = obfuscator.obfuscate(text, SensitivityLevel.CONFIDENTIAL)
print(obfuscated)  # "Email [EMAIL] for access"
```

## Troubleshooting

### Permission Denied Errors

Check:
1. User has required roles for the workflow
2. Workflow allows access to the requested stores
3. User is not in denied_roles list

### No Results Returned

Check:
1. Knowledge stores are initialized
2. Stores contain data
3. Query matches available documents
4. User has permission to view results

### Integration Issues

Check:
1. API keys are configured correctly
2. Network connectivity to external services
3. MCP servers are running and accessible

## Next Steps

1. **Production Deployment**: See main README for deployment guide
2. **Custom MCP Connectors**: Implement connectors for your knowledge sources
3. **Identity Provider Integration**: Connect to Azure AD, Okta, etc.
4. **Compliance Setup**: Configure audit retention and reporting
