# Integration Tests

Integration tests for the Knowledge System with Consilience services.

## Overview

These tests verify that the Knowledge System integrates correctly with:
- **Database** (PostgreSQL with pgvector)
- **API Service** (Consilience main API)
- **Ingestion Service** (document processing)
- **Frontend** (Vue.js application)

## Running Tests

### Quick Start

```bash
./scripts/run_integration_tests.sh
```

This script will:
1. Build and start all services with docker-compose
2. Wait for services to be ready
3. Run integration tests
4. Display results and logs

### Manual Testing

```bash
# Start services
docker-compose up -d

# Wait for services (optional)
./scripts/wait_for_services.sh

# Run tests
pytest tests/integration/test_knowledge_system.py -v
```

### Running Specific Tests

```bash
# Run only health check tests
pytest tests/integration/test_knowledge_system.py::TestKnowledgeSystemIntegration::test_health_check -v

# Run performance tests
pytest tests/integration/test_knowledge_system.py::TestPerformance -v

# Run with detailed output
pytest tests/integration/test_knowledge_system.py -v -s
```

## Test Categories

### 1. Service Health Tests
- `test_health_check` - Verify service is running
- `test_list_workflows` - Check workflow availability
- `test_list_knowledge_stores` - Verify store listing

### 2. Workflow Execution Tests
- `test_execute_workflow_query` - Execute basic query
- `test_permission_denied` - Verify RBAC enforcement
- `test_workflow_with_multiple_stores` - Multi-store access

### 3. Integration Tests
- `test_integration_with_api_service` - API service connectivity
- `test_integration_with_ingestion_service` - Ingestion connectivity
- `test_audit_statistics` - Audit logging integration

### 4. Security Tests
- `test_permission_denied` - RBAC enforcement
- `test_pii_obfuscation` - PII protection

### 5. Performance Tests
- `test_query_response_time` - Response time check
- `test_concurrent_queries` - Concurrent load handling

## Test Environment

### Service Endpoints

- **Knowledge System**: http://localhost:8100
- **API Service**: http://localhost:8000
- **Ingestion Service**: http://localhost:5050
- **Frontend**: http://localhost:8080
- **Database**: postgresql://localhost:5433/graphragdb

### Environment Variables

```bash
export KNOWLEDGE_SYSTEM_URL=http://localhost:8100
export API_SERVICE_URL=http://localhost:8000
export INGESTION_SERVICE_URL=http://localhost:5050
export DATABASE_URL=postgresql://graphraguser:graphragpassword@localhost:5433/graphragdb
```

## Test Data

### Demo Users

- **demo@company.com** - Employee + Demo User
- **alice@company.com** - Employee
- **bob@company.com** - Employee + Manager

### Demo Workflows

- **meeting_tracker** - Meetings only (metadata_only PII)
- **project_assistant** - Multiple stores (partial PII)
- **confidential_research** - Confidential (requires analyst role)
- **demo_workflow** - Multi-store access

## Expected Results

All tests should pass when services are healthy:

```
✓ test_health_check
✓ test_list_workflows
✓ test_list_knowledge_stores
✓ test_execute_workflow_query
✓ test_permission_denied
✓ test_audit_statistics
✓ test_integration_with_api_service
✓ test_integration_with_ingestion_service
✓ test_workflow_with_multiple_stores
✓ test_pii_obfuscation
✓ test_query_response_time
✓ test_concurrent_queries
```

## Troubleshooting

### Services Not Starting

```bash
# Check service logs
docker-compose logs knowledge-system
docker-compose logs api-service
docker-compose logs db

# Restart services
docker-compose restart knowledge-system
```

### Tests Timing Out

Increase timeout in test or wait longer for services:

```python
# In test file
async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)):
    ...
```

### Database Connection Errors

```bash
# Check database is healthy
docker-compose ps db

# Check database connection
psql postgresql://graphraguser:graphragpassword@localhost:5433/graphragdb -c "SELECT 1"
```

### Permission Errors

Verify RBAC is configured:

```bash
# Check workflows
curl http://localhost:8100/workflows

# Check stores
curl http://localhost:8100/stores
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run integration tests
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          ./scripts/run_integration_tests.sh
```

### GitLab CI

```yaml
integration_tests:
  stage: test
  script:
    - ./scripts/run_integration_tests.sh
  services:
    - docker:dind
  variables:
    OPENAI_API_KEY: $OPENAI_API_KEY
```

## Performance Benchmarks

Expected performance:
- Health check: < 100ms
- List workflows: < 200ms
- Simple query: < 2s
- Complex query: < 5s
- Concurrent queries (5): < 10s total

## Debugging

### Enable Verbose Logging

```bash
# In docker-compose.yml
environment:
  LOG_LEVEL: DEBUG
```

### Access Service Logs

```bash
# Knowledge System
docker-compose logs -f knowledge-system

# All services
docker-compose logs -f

# Last 50 lines
docker-compose logs --tail=50 knowledge-system
```

### Interactive Debugging

```bash
# Enter service container
docker-compose exec knowledge-system /bin/bash

# Check service status
curl http://localhost:8100/health

# Check workflows
curl http://localhost:8100/workflows
```

## Adding New Tests

1. Add test function to `test_knowledge_system.py`
2. Use `@pytest.mark.asyncio` for async tests
3. Use `wait_for_services` fixture
4. Add documentation here

Example:

```python
@pytest.mark.asyncio
async def test_new_feature(self, wait_for_services):
    """Test description"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{KNOWLEDGE_SYSTEM_URL}/new-endpoint") as response:
            assert response.status == 200
            data = await response.json()
            assert "expected_field" in data
```

## Maintenance

### Update Test Data

```bash
# Update workflow configurations
vim src/knowledge_system/examples/workflows.yaml

# Rebuild and test
docker-compose up -d --build knowledge-system
./scripts/run_integration_tests.sh
```

### Clean Up

```bash
# Stop services
docker-compose down

# Remove volumes
docker-compose down -v

# Clean Docker system
docker system prune -f
```
