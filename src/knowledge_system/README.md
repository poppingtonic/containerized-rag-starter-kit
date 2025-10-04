# Enterprise Knowledge System Architecture

This module extends Consilience with enterprise-grade multi-tenant knowledge management capabilities.

## Architecture Overview

### Core Components

1. **Knowledge Store Abstraction Layer** (`stores/`)
   - Multiple knowledge store types (meetings, emails, documents, confidential)
   - MCP-based connectors for each store
   - Unified query interface

2. **RBAC Permission System** (`rbac/`)
   - Role-based access control
   - Permission gating at query and retrieval time
   - Integration with Azure AD/Entra ID
   - Workflow-based permission sets

3. **Audit & Compliance** (`audit/`)
   - Comprehensive audit logging
   - Data veracity tracking
   - Access pattern analysis
   - Compliance reporting

4. **PII Protection** (`privacy/`)
   - Automatic PII detection and obfuscation
   - Metadata-only access modes
   - Configurable sensitivity levels

5. **Workflow Management** (`workflows/`, `workflow_managers/`)
   - YAML-based workflow definitions
   - Context-aware tool routing
   - Workflow-specific knowledge store access
   - Integration with Power Automate & Copilot Studio
   - **LangGraph Studio integration** for visual graph workflows
   - **Dify integration** for low-code workflow building

## Knowledge Store Types

### Meeting Transcripts Store
- Stores: meeting notes, transcripts, recordings metadata
- Access: time-based, participant-based
- Indexing: speaker, date, topics, attendees

### Email Store
- Stores: email messages, threads, metadata
- Access: sender/recipient based, folder-based
- Indexing: from/to, subject, date, labels

### Shared Documents Store
- Stores: org-wide documents, wikis, public files
- Access: department/team based
- Indexing: author, tags, categories, date

### Confidential Data Store
- Stores: market data, financial info, sensitive docs
- Access: strict RBAC, clearance-level based
- Indexing: classification level, owner, expiry

### Project Team Store
- Stores: project-specific documents, notes, artifacts
- Access: project membership based
- Indexing: project ID, team, sprint, status

## Security Model

### Multi-Layer Permission Gating

```
Query Request
    ↓
1. Workflow Identification (which tools can be used?)
    ↓
2. Role Validation (does user have required role?)
    ↓
3. Store Permission Check (can user access this store?)
    ↓
4. Document-Level ACL (can user see this doc?)
    ↓
5. PII Filter (obfuscate sensitive data)
    ↓
6. Audit Log (record access)
    ↓
Response
```

### Prompt Injection Prevention
- Input sanitization at workflow boundary
- Separate system/user context
- No direct LLM access to raw permissions
- Metadata extraction in isolated service

## Integration Points

### Power Automate
- REST API with OAuth2 authentication
- Webhook support for async operations
- Standard connector format

### Copilot Studio
- Microsoft Bot Framework adapter
- Conversational flow integration
- SSO with Microsoft 365

### SharePoint
- Graph API integration
- Site/library level permissions mapping
- Change notification subscriptions

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway (Auth)                        │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
    ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
    │Workflow │    │  RBAC   │    │  Audit  │
    │ Router  │    │ Service │    │ Logger  │
    └────┬────┘    └────┬────┘    └────┬────┘
         │               │               │
         └───────────────┼───────────────┘
                         │
              ┌──────────┴──────────┐
              │   Knowledge Store   │
              │   Manager (MCP)     │
              └──────────┬──────────┘
                         │
         ┌───────────────┼───────────────────┬──────────┐
         │               │                   │          │
    ┌────▼────┐    ┌────▼────┐    ┌────────▼───┐  ┌───▼──────┐
    │Meetings │    │ Emails  │    │Shared Docs │  │Project   │
    │ Store   │    │ Store   │    │   Store    │  │  Stores  │
    └─────────┘    └─────────┘    └────────────┘  └──────────┘
```

## Configuration

### Environment Variables

```bash
# RBAC Configuration
RBAC_PROVIDER=azure_ad  # or okta, auth0
RBAC_TENANT_ID=your-tenant-id
RBAC_ENABLE_WORKFLOW_ISOLATION=true

# Audit Configuration
AUDIT_LOG_LEVEL=detailed  # basic, detailed, forensic
AUDIT_RETENTION_DAYS=365
AUDIT_EXPORT_ENDPOINT=https://audit.company.com

# PII Protection
PII_DETECTION_ENABLED=true
PII_OBFUSCATION_LEVEL=metadata_only  # full, partial, metadata_only
PII_PATTERNS_CONFIG=/config/pii_patterns.json

# Knowledge Stores
ENABLE_MEETINGS_STORE=true
ENABLE_EMAIL_STORE=true
ENABLE_CONFIDENTIAL_STORE=true
MEETINGS_STORE_PATH=/data/meetings
EMAIL_STORE_CONNECTOR=microsoft_graph

# Workflow Configuration
WORKFLOW_ROUTING_ENABLED=true
WORKFLOW_CONFIG_PATH=/config/workflows.yaml

# Microsoft Integration
MICROSOFT_TENANT_ID=your-tenant-id
MICROSOFT_CLIENT_ID=your-client-id
MICROSOFT_CLIENT_SECRET=your-secret
ENABLE_POWER_AUTOMATE=true
ENABLE_COPILOT_STUDIO=true
```

## Usage Examples

### Creating a Workflow-Restricted Query

```python
from knowledge_system.workflows import WorkflowRouter
from knowledge_system.rbac import RBACService

# Initialize with user context
router = WorkflowRouter(
    user_id="user@company.com",
    workflow="meeting_tracker",
    roles=["employee", "team_member"]
)

# Query will only access meetings store
result = await router.query(
    "What were the action items from yesterday's standup?",
    max_results=5
)
```

### Setting Up Store Permissions

```yaml
# workflows.yaml
workflows:
  meeting_tracker:
    description: "Track meeting notes and action items"
    allowed_stores:
      - meetings
    required_roles:
      - employee
    pii_level: metadata_only

  project_team_assistant:
    description: "Project-specific knowledge assistant"
    allowed_stores:
      - project_teams
      - shared_documents
    required_roles:
      - project_member
    pii_level: partial

  confidential_research:
    description: "Access to market data and research"
    allowed_stores:
      - confidential
    required_roles:
      - analyst
      - manager
    pii_level: full
    audit_level: forensic
```

## Development Roadmap

### Phase 1: Foundation (Weeks 1-2)
- [ ] Knowledge store abstraction layer
- [ ] Basic RBAC service
- [ ] Audit logging infrastructure

### Phase 2: Core Features (Weeks 3-4)
- [ ] Multiple knowledge store implementations
- [ ] Workflow routing system
- [ ] PII detection and obfuscation

### Phase 3: Integration (Weeks 5-6)
- [ ] Microsoft Graph API connector
- [ ] Power Automate compatibility
- [ ] Copilot Studio adapter

### Phase 4: Enterprise (Weeks 7-8)
- [ ] Advanced audit analytics
- [ ] Data veracity monitoring
- [ ] Compliance reporting dashboard

## Security Considerations

1. **Zero Trust Architecture**: Never trust, always verify
2. **Defense in Depth**: Multiple security layers
3. **Least Privilege**: Users get minimum required access
4. **Audit Everything**: Complete access trail
5. **Data Sovereignty**: Control where data lives
6. **Encryption**: At rest and in transit

## Testing Strategy

1. Unit tests for each component
2. Integration tests for workflow scenarios
3. Security penetration testing
4. Performance benchmarking
5. Compliance validation

## Monitoring & Observability

- Prometheus metrics for query patterns
- Grafana dashboards for access analytics
- Elasticsearch for audit log search
- Alerting for security anomalies
