# Knowledge System Quick Start Guide

Get the Enterprise Knowledge System running with Consilience in 5 minutes.

## Prerequisites

- Docker and Docker Compose installed
- OpenAI API key
- 8GB RAM recommended

## Quick Start

### 1. Set Environment Variables

```bash
# Create .env file
cat > .env << EOF
OPENAI_API_KEY=your-openai-api-key-here
EOF
```

### 2. Start All Services

```bash
# Start everything (includes Knowledge System)
docker-compose up -d

# Or start just Knowledge System
docker-compose up -d knowledge-system
```

### 3. Verify Services

```bash
# Check all services are running
docker-compose ps

# Check Knowledge System health
curl http://localhost:8100/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00",
  "components": {
    "store_manager": true,
    "rbac_service": true,
    "audit_logger": true,
    "workflow_router": true
  }
}
```

### 4. Run Integration Tests

```bash
./scripts/run_integration_tests.sh
```

## Service Endpoints

| Service | URL | Description |
|---------|-----|-------------|
| Knowledge System | http://localhost:8100 | Main knowledge system API |
| API Service | http://localhost:8000 | Consilience API |
| Frontend | http://localhost:8080 | Web interface |
| Ingestion | http://localhost:5050 | Document processing |
| Database | postgresql://localhost:5433 | PostgreSQL + pgvector |

## Basic Usage

### List Available Workflows

```bash
curl http://localhost:8100/workflows \
  -H "X-User-Roles: employee"
```

Response:
```json
[
  {
    "workflow_id": "meeting_tracker",
    "name": "Meeting Tracker",
    "description": "Track meeting notes and action items",
    "allowed_stores": ["meetings"],
    "required_roles": ["employee"],
    "pii_level": "metadata_only"
  }
]
```

### Execute a Query

```bash
curl -X POST http://localhost:8100/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the latest updates?",
    "workflow_id": "demo_workflow",
    "user_id": "demo@company.com",
    "user_email": "demo@company.com",
    "user_roles": ["employee", "demo_user"],
    "max_results": 5
  }'
```

Response:
```json
{
  "success": true,
  "workflow_id": "demo_workflow",
  "query": "What are the latest updates?",
  "answer": "Based on available information...",
  "stores_queried": ["meetings", "emails"],
  "total_results": 3,
  "execution_time_ms": 1234.5,
  "obfuscated": false
}
```

### List Knowledge Stores

```bash
curl http://localhost:8100/stores \
  -H "X-User-Roles: employee"
```

### Get Audit Statistics

```bash
curl http://localhost:8100/audit/statistics?days=7
```

## Testing Different Scenarios

### 1. Basic Employee Query

```bash
curl -X POST http://localhost:8100/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show recent meetings",
    "workflow_id": "meeting_tracker",
    "user_id": "alice@company.com",
    "user_email": "alice@company.com",
    "user_roles": ["employee"]
  }'
```

### 2. Manager Query (Multiple Stores)

```bash
curl -X POST http://localhost:8100/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Project status update",
    "workflow_id": "project_assistant",
    "user_id": "bob@company.com",
    "user_email": "bob@company.com",
    "user_roles": ["employee", "manager"]
  }'
```

### 3. Confidential Query (Requires Analyst Role)

```bash
# This will FAIL - user lacks required role
curl -X POST http://localhost:8100/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Market analysis",
    "workflow_id": "confidential_research",
    "user_id": "alice@company.com",
    "user_email": "alice@company.com",
    "user_roles": ["employee"]
  }'
```

Expected error:
```json
{
  "success": false,
  "error": "Permission denied: User lacks required roles: ['analyst']"
}
```

## Adding Documents

### 1. Add a Document to Ingest

```bash
# Copy document to data directory
cp your-document.pdf ./data/

# Check ingestion status
curl http://localhost:5050/status
```

### 2. Trigger Processing

```bash
curl -X POST http://localhost:5050/trigger-ingestion
```

### 3. Query the New Document

```bash
# Wait for processing to complete
sleep 30

# Query for the content
curl -X POST http://localhost:8100/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Information from recent document",
    "workflow_id": "demo_workflow",
    "user_id": "demo@company.com",
    "user_email": "demo@company.com",
    "user_roles": ["employee", "demo_user"]
  }'
```

## Configuring Workflows

### Edit Workflow Configuration

```bash
# Edit workflows
vim src/knowledge_system/examples/workflows.yaml

# Restart service to load changes
docker-compose restart knowledge-system
```

### Example: Add New Workflow

```yaml
workflows:
  custom_workflow:
    name: "Custom Workflow"
    description: "My custom workflow"
    allowed_stores:
      - meetings
      - emails
    required_roles:
      - employee
    pii_level: partial
    audit_level: detailed
    max_results: 20
    active: true
```

## Monitoring

### View Logs

```bash
# Knowledge System logs
docker-compose logs -f knowledge-system

# All services
docker-compose logs -f

# Last 50 lines
docker-compose logs --tail=50 knowledge-system
```

### Check Service Health

```bash
# All services
for service in knowledge-system api-service ingestion-service; do
  echo "=== $service ==="
  docker-compose ps $service
done
```

### Monitor Resource Usage

```bash
docker stats
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose logs knowledge-system

# Common issue: Port already in use
lsof -i :8100

# Restart service
docker-compose restart knowledge-system
```

### Database Connection Errors

```bash
# Check database is healthy
docker-compose ps db

# Test connection
docker-compose exec db psql -U graphraguser -d graphragdb -c "SELECT 1"
```

### Workflow Not Found

```bash
# List available workflows
curl http://localhost:8100/workflows -H "X-User-Roles: employee"

# Check configuration
cat src/knowledge_system/examples/workflows.yaml
```

### Permission Denied

```bash
# Verify user has required roles
# Check workflow requirements
curl http://localhost:8100/workflows | python3 -m json.tool
```

## Advanced Configuration

### Enable LangGraph Studio Integration

```bash
# Install LangGraph Studio
pip install langgraph-studio

# Start LangGraph Studio
langgraph studio

# Set environment variable
export LANGGRAPH_API_URL=http://localhost:8123

# Restart Knowledge System
docker-compose restart knowledge-system
```

### Enable Dify Integration

```bash
# Get Dify API key from dify.ai
export DIFY_API_KEY=app-your-key
export DIFY_API_URL=https://api.dify.ai/v1

# Restart Knowledge System
docker-compose restart knowledge-system
```

### Enable Forensic Audit Logging

```yaml
# In docker-compose.yml
environment:
  AUDIT_LEVEL: forensic  # basic, detailed, forensic
```

## Cleanup

### Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

### Remove Images

```bash
# Remove knowledge system image
docker rmi consilience-knowledge-system

# Clean up Docker system
docker system prune -f
```

## Next Steps

1. **Customize Workflows**: Edit `src/knowledge_system/examples/workflows.yaml`
2. **Add Knowledge Stores**: Implement custom MCP connectors
3. **Integrate Identity Provider**: Configure Azure AD or Okta
4. **Set Up Monitoring**: Add Prometheus metrics
5. **Production Deployment**: Review security settings

## Documentation

- **Architecture**: `src/knowledge_system/README.md`
- **Workflow Managers**: `src/knowledge_system/WORKFLOW_MANAGERS.md`
- **Integration Tests**: `tests/integration/README.md`
- **API Reference**: http://localhost:8100/docs (when running)

## Support

For issues:
1. Check logs: `docker-compose logs knowledge-system`
2. Run integration tests: `./scripts/run_integration_tests.sh`
3. Review documentation in `src/knowledge_system/`

## Production Checklist

Before deploying to production:

- [ ] Configure proper authentication (Azure AD/Okta)
- [ ] Set up SSL/TLS certificates
- [ ] Configure database backups
- [ ] Set up monitoring and alerting
- [ ] Review and customize workflows
- [ ] Configure log retention
- [ ] Set up audit log exports
- [ ] Review PII obfuscation settings
- [ ] Load test with expected query volume
- [ ] Configure firewall rules
- [ ] Set up disaster recovery plan

---

**You're ready!** The Knowledge System is now running alongside Consilience. 🚀
