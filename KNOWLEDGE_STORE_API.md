# Knowledge Store Management API

This guide explains how to dynamically create and manage knowledge stores in the Consilience system, and how they share database resources efficiently.

## Overview

The Knowledge Store Management API allows you to create and manage multiple isolated knowledge stores that all share the same PostgreSQL + pgvector database infrastructure. This provides:

- **Multi-tenant support** - Each store is logically isolated by `store_id`
- **Resource efficiency** - All stores share the same vector search infrastructure
- **No duplication** - Embeddings and indexes are reused across stores
- **Dynamic provisioning** - Create new stores at runtime via REST API
- **Unified management** - Single database, consistent backup/recovery

## Architecture

### Database Partitioning

Instead of creating separate tables for each store, all stores share these tables:

```sql
-- Existing table structure
document_chunks (
    chunk_id VARCHAR PRIMARY KEY,
    source_file VARCHAR,
    content TEXT,
    chunk_index INTEGER,
    content_hash VARCHAR,
    store_id VARCHAR(255),  -- Added for partitioning
    created_at TIMESTAMP
)

chunk_embeddings (
    chunk_id VARCHAR PRIMARY KEY REFERENCES document_chunks(chunk_id),
    embedding vector(1536)  -- pgvector type
)
```

The `store_id` column partitions data logically while sharing infrastructure:
- **Index**: `idx_chunks_store_id` for efficient filtering
- **Queries**: Always filtered by `store_id = 'your_store'`
- **Isolation**: Each store only sees its own data

### How Vector Search is Shared

Vector similarity search works across all stores but returns filtered results:

```python
# Query example - filtered by store_id
SELECT
    c.*,
    (e.embedding <=> query_embedding::vector) as distance
FROM document_chunks c
JOIN chunk_embeddings e ON c.chunk_id = e.chunk_id
WHERE c.store_id = 'meetings_store'  -- Partition filter
ORDER BY e.embedding <=> query_embedding::vector
LIMIT 10
```

This means:
- All embeddings live in one `chunk_embeddings` table
- pgvector indexes work across all stores
- Queries are filtered to show only data from the requested store
- No duplicate embeddings or infrastructure

## API Endpoints

The Knowledge System Service exposes these endpoints on port **8100**:

### 1. Create a Knowledge Store

**Endpoint**: `POST /stores`

Creates a new knowledge store that shares the database.

```bash
curl -X POST http://localhost:8100/stores \
  -H "Content-Type: application/json" \
  -d '{
    "store_id": "meetings_2024",
    "name": "2024 Meetings",
    "description": "Meeting transcripts and notes from 2024",
    "store_type": "meetings",
    "requires_roles": ["employee"],
    "pii_level": "metadata_only",
    "audit_level": "detailed",
    "connection_config": {}
  }'
```

**Request Fields**:
- `store_id`: Unique identifier (used for partitioning)
- `name`: Human-readable name
- `description`: Store description
- `store_type`: Type of store (meetings, emails, documents, etc.)
- `requires_roles`: List of roles required to access
- `pii_level`: PII protection level (none, partial, full, metadata_only)
- `audit_level`: Audit logging level (basic, detailed, forensic)
- `connection_config`: Optional store-specific configuration

**Response**:
```json
{
  "store_id": "meetings_2024",
  "name": "2024 Meetings",
  "description": "Meeting transcripts and notes from 2024",
  "store_type": "meetings",
  "enabled": true,
  "requires_roles": ["employee"],
  "pii_level": "metadata_only",
  "audit_level": "detailed",
  "created_at": "2024-10-08T17:45:00.000000",
  "statistics": {
    "document_count": 0,
    "chunk_count": 0
  }
}
```

### 2. List All Stores

**Endpoint**: `GET /stores/all`

Lists all registered knowledge stores with statistics.

```bash
curl http://localhost:8100/stores/all
```

**Response**:
```json
[
  {
    "store_id": "meetings_2024",
    "name": "2024 Meetings",
    "store_type": "meetings",
    "enabled": true,
    "statistics": {
      "document_count": 15,
      "chunk_count": 243,
      "oldest_document": "2024-01-05T10:00:00",
      "newest_document": "2024-10-08T15:30:00"
    }
  },
  {
    "store_id": "confidential_docs",
    "name": "Confidential Documents",
    "store_type": "documents",
    "enabled": true,
    "statistics": {
      "document_count": 8,
      "chunk_count": 156
    }
  }
]
```

### 3. Get Store Details

**Endpoint**: `GET /stores/{store_id}`

Get detailed information about a specific store.

```bash
curl http://localhost:8100/stores/meetings_2024
```

### 4. Delete a Store

**Endpoint**: `DELETE /stores/{store_id}`

Removes a store from the manager. **Note**: Data remains in the database.

```bash
curl -X DELETE http://localhost:8100/stores/meetings_2024
```

**Response**:
```json
{
  "success": true,
  "store_id": "meetings_2024",
  "message": "Store unregistered successfully. Data remains in database."
}
```

To permanently delete data, you would need to run:
```sql
DELETE FROM document_chunks WHERE store_id = 'meetings_2024';
```

### 5. Check Store Health

**Endpoint**: `GET /stores/{store_id}/health`

Check if a store is healthy and can be queried.

```bash
curl http://localhost:8100/stores/meetings_2024/health
```

**Response**:
```json
{
  "store_id": "meetings_2024",
  "healthy": true,
  "error": null
}
```

### 6. Index Documents

**Endpoint**: `POST /stores/{store_id}/documents`

Add a document to a knowledge store. The document will be:
1. Chunked into smaller pieces (512 words with 50-word overlap)
2. Embedded using OpenAI's `text-embedding-ada-002`
3. Stored with `store_id` partition
4. Indexed for vector similarity search

```bash
curl -X POST http://localhost:8100/stores/meetings_2024/documents \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "meeting_20241008",
    "title": "Q4 Planning Meeting",
    "content": "Today we discussed Q4 goals and priorities...",
    "author": "alice@company.com",
    "tags": ["planning", "q4", "strategy"],
    "metadata": {
      "date": "2024-10-08",
      "participants": ["Alice", "Bob", "Carol"]
    }
  }'
```

**Request Fields**:
- `doc_id`: Unique document identifier
- `title`: Document title
- `content`: Full document text
- `author`: Optional author
- `tags`: Optional list of tags
- `metadata`: Optional custom metadata

**Response**:
```json
{
  "success": true,
  "doc_id": "meeting_20241008",
  "store_id": "meetings_2024",
  "message": "Document indexed successfully"
}
```

### 7. Get Store Statistics

**Endpoint**: `GET /stores/{store_id}/statistics`

Get detailed statistics about a store's contents.

```bash
curl http://localhost:8100/stores/meetings_2024/statistics
```

**Response**:
```json
{
  "document_count": 15,
  "chunk_count": 243,
  "oldest_document": "2024-01-05T10:00:00",
  "newest_document": "2024-10-08T15:30:00"
}
```

## How Stores Share Resources

### Vector Search Infrastructure

All stores share the same pgvector infrastructure:

```python
# DatabaseBackedStore implementation
async def query(self, query_text: str, user_id: str, user_roles: List[str],
                max_results: int = 10) -> List[QueryResult]:
    # Generate query embedding (shared OpenAI API)
    query_embedding = await self._generate_embedding(query_text)

    # Vector search filtered by store_id
    cur.execute("""
        SELECT c.*, (e.embedding <=> %s::vector) as distance
        FROM document_chunks c
        JOIN chunk_embeddings e ON c.chunk_id = e.chunk_id
        WHERE c.store_id = %s  -- Partitioning filter
        ORDER BY e.embedding <=> %s::vector
        LIMIT %s
    """, (query_embedding, self.metadata.store_id, query_embedding, max_results))
```

### Benefits of This Approach

1. **Efficiency**: Single pgvector index serves all stores
2. **No Duplication**: Embeddings stored once, reused efficiently
3. **Unified Backup**: Single database to backup/restore
4. **Easy Scaling**: Add stores without infrastructure changes
5. **Consistent Performance**: All stores benefit from optimized indexes

### Resource Usage

When you create a new store:
- **No new tables** are created
- **No new indexes** are created
- **No database migrations** are needed
- Only metadata is registered in the `KnowledgeStoreManager`
- Data is partitioned using the existing `store_id` column

## Example Workflow

Here's how to set up multiple knowledge stores:

```bash
# 1. Start the services
docker-compose up -d

# 2. Wait for services to be ready
sleep 10

# 3. Create a meetings store
curl -X POST http://localhost:8100/stores \
  -H "Content-Type: application/json" \
  -d '{
    "store_id": "meetings",
    "name": "Meeting Transcripts",
    "description": "All team meeting transcripts",
    "store_type": "meetings",
    "requires_roles": ["employee"],
    "pii_level": "partial",
    "audit_level": "detailed"
  }'

# 4. Create an emails store
curl -X POST http://localhost:8100/stores \
  -H "Content-Type: application/json" \
  -d '{
    "store_id": "emails",
    "name": "Email Archive",
    "description": "Archived company emails",
    "store_type": "emails",
    "requires_roles": ["employee", "manager"],
    "pii_level": "full",
    "audit_level": "forensic"
  }'

# 5. Create a confidential documents store
curl -X POST http://localhost:8100/stores \
  -H "Content-Type: application/json" \
  -d '{
    "store_id": "confidential",
    "name": "Confidential Documents",
    "description": "Sensitive company documents",
    "store_type": "documents",
    "requires_roles": ["executive"],
    "pii_level": "full",
    "audit_level": "forensic"
  }'

# 6. Index a document to the meetings store
curl -X POST http://localhost:8100/stores/meetings/documents \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "meeting_001",
    "title": "Engineering Standup",
    "content": "Discussed sprint progress and blockers...",
    "tags": ["standup", "engineering"]
  }'

# 7. Query the meetings store via workflows
curl -X POST http://localhost:8100/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What were the main blockers discussed?",
    "workflow_id": "meeting_tracker",
    "user_id": "alice@company.com",
    "user_email": "alice@company.com",
    "user_roles": ["employee"]
  }'

# 8. Check store statistics
curl http://localhost:8100/stores/meetings/statistics
```

## Integration with Workflows

Workflows can access specific stores based on configuration:

```yaml
# workflows.yaml
workflows:
  meeting_tracker:
    name: "Meeting Insights"
    description: "Search and analyze meeting transcripts"
    allowed_stores:
      - meetings  # Only accesses meetings store
    required_roles:
      - employee
    pii_level: partial
    audit_level: detailed

  email_search:
    name: "Email Search"
    description: "Search archived emails"
    allowed_stores:
      - emails  # Only accesses emails store
    required_roles:
      - employee
      - manager
    pii_level: full
    audit_level: forensic

  executive_dashboard:
    name: "Executive Dashboard"
    description: "Access all data sources"
    allowed_stores:
      - meetings
      - emails
      - confidential  # Multi-store access
    required_roles:
      - executive
    pii_level: none
    audit_level: forensic
```

## Security and Access Control

### RBAC Integration

Each store can specify required roles:

```python
store = DatabaseBackedStore(
    metadata=StoreMetadata(
        store_id="confidential",
        requires_roles=["executive", "legal"]  # Only these roles can access
    ),
    ...
)
```

Access is checked via `check_permission()`:

```python
async def check_permission(self, doc_id: str, user_id: str,
                           user_roles: List[str]) -> bool:
    required_roles = self.metadata.requires_roles
    if not required_roles:
        return True  # Public store

    # Check if user has any of the required roles
    return any(role in user_roles for role in required_roles)
```

### PII Protection

Each store can have its own PII protection level:

- `none`: No PII protection
- `partial`: Redact PII in results
- `full`: Full PII obfuscation
- `metadata_only`: Return only metadata, no content

### Audit Logging

All store operations are logged:

```python
await audit_logger.log_event(
    event_type="document_indexed",
    user_id=user_id,
    resource_id=f"{store_id}/{doc_id}",
    action="index",
    result="success",
    details={"store": store_id, "doc_id": doc_id}
)
```

## Monitoring and Management

### Health Checks

Monitor store health:

```bash
# Check specific store
curl http://localhost:8100/stores/meetings/health

# Check overall system health
curl http://localhost:8100/health
```

### Statistics

Track usage and growth:

```bash
# Per-store statistics
curl http://localhost:8100/stores/meetings/statistics

# System-wide audit statistics
curl http://localhost:8100/audit/statistics?days=7
```

### Database Queries

Direct database queries for troubleshooting:

```sql
-- See all stores and their document counts
SELECT
    store_id,
    COUNT(DISTINCT source_file) as docs,
    COUNT(*) as chunks
FROM document_chunks
GROUP BY store_id;

-- Find largest stores
SELECT
    store_id,
    COUNT(*) as chunk_count,
    pg_size_pretty(pg_total_relation_size('document_chunks')) as total_size
FROM document_chunks
GROUP BY store_id
ORDER BY chunk_count DESC;

-- Check index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as times_used,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes
WHERE tablename = 'document_chunks';
```

## Best Practices

1. **Store IDs**: Use descriptive, unique identifiers (e.g., `meetings_2024`, `emails_archive`)

2. **Access Control**: Always specify `requires_roles` for sensitive stores

3. **PII Protection**: Set appropriate `pii_level` based on data sensitivity

4. **Audit Level**: Use `forensic` for stores with sensitive data

5. **Document IDs**: Use consistent naming schemes (e.g., `meeting_YYYYMMDD`, `email_<timestamp>`)

6. **Monitoring**: Regularly check store health and statistics

7. **Cleanup**: Unregister unused stores, but consider data retention policies before deleting data

8. **Performance**: Monitor database size and query performance as stores grow

9. **Backup**: Since all stores share one database, regular backups are critical

10. **Documentation**: Document which workflows access which stores

## Troubleshooting

### Store Not Found

```json
{
  "detail": "Store meetings_2024 not found"
}
```

**Solution**: The store hasn't been registered. Create it first with `POST /stores`.

### Permission Denied

```json
{
  "error": "Permission denied: User lacks required roles"
}
```

**Solution**: User doesn't have required roles. Check `requires_roles` in store metadata.

### Database Connection Failed

```json
{
  "healthy": false,
  "error": "Not initialized"
}
```

**Solution**: Check DATABASE_URL environment variable and PostgreSQL connection.

### Empty Results

If queries return no results:
1. Check if documents were indexed: `GET /stores/{store_id}/statistics`
2. Verify `store_id` partitioning: `SELECT DISTINCT store_id FROM document_chunks;`
3. Check query permissions

## Summary

The Knowledge Store Management API provides:

- **Dynamic store creation** via REST API
- **Database resource sharing** through `store_id` partitioning
- **Efficient vector search** across all stores
- **RBAC, PII protection, and audit logging** for each store
- **Multi-tenant support** with logical isolation
- **Unified management** and monitoring

All stores share the same PostgreSQL + pgvector infrastructure, making it efficient and easy to scale.
