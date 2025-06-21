# Consilience MCP Server

This is a Model Context Protocol (MCP) server that exposes Consilience's document query and document ingestion capabilities.

## Overview

The MCP server provides programmatic access to:
- Document querying with filtered results
- Document ingestion management
- Memory/cache management
- System status monitoring

## Available Tools

### Query Tools

1. **query_documents** - Full-featured document query with filtered results
   - Supports memory caching
   - Query amplification
   - Smart chunk selection
   - Returns answers with citations, entities, and verification scores

2. **simple_query** - Basic document query without advanced features
   - Faster but less comprehensive
   - No memory caching or amplification

### Ingestion Tools

3. **trigger_ingestion** - Trigger document processing for new files in the data directory

4. **ingestion_status** - Get current status of the ingestion service

5. **process_file** - Process a specific file

6. **get_ingestion_progress** - Get detailed ingestion statistics from the database

7. **list_documents** - List all documents in the database

### System Tools

8. **get_memory_stats** - Get query cache statistics

9. **clear_memory** - Clear all cached queries

## Usage

### Running with Docker Compose

The MCP server is included in the docker-compose configuration:

```bash
# Start all services including MCP server
docker compose up -d

# View MCP server logs
docker compose logs -f mcp-server

# Connect to MCP server
docker compose exec mcp-server /bin/bash
```

### Connecting from Claude Desktop

Add this configuration to your Claude Desktop config:

```json
{
  "mcpServers": {
    "consilience": {
      "command": "docker",
      "args": ["compose", "exec", "-T", "mcp-server", "python", "/app/mcp_server/server.py"],
      "cwd": "/path/to/consilience"
    }
  }
}
```

### Example Usage

```python
# Query documents
result = await mcp.call_tool("query_documents", {
    "query": "What are the main findings about climate change?",
    "max_results": 5,
    "use_amplification": true
})

# Trigger ingestion
await mcp.call_tool("trigger_ingestion", {})

# Check ingestion status
status = await mcp.call_tool("ingestion_status", {})

# List documents
docs = await mcp.call_tool("list_documents", {"limit": 20})
```

## Environment Variables

- `DATABASE_URL` - PostgreSQL connection string
- `OPENAI_API_KEY` - OpenAI API key for embeddings and generation
- `INGESTION_SERVICE_URL` - URL of the ingestion service (default: http://ingestion-service:5050)

## Development

To run the MCP server locally:

```bash
cd mcp_server
pip install -r requirements.txt
export PYTHONPATH=/path/to/consilience
python server.py
```

## Architecture

The MCP server acts as a bridge between MCP clients and the Consilience system:

```
MCP Client <-> MCP Server <-> Document Services
                           |-> Query Service
                           |-> Ingestion Service
                           |-> Database
```

It reuses the existing service implementations from the API service, ensuring consistency across interfaces.