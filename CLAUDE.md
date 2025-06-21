# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Consilience is a containerized application that generates paragraph answers with references based on user queries, powered by GraphRAG technology. The system processes documents, builds a knowledge graph of entities and their relationships, and provides comprehensive answers with citations.

## Common Commands

### Running the Application

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# View logs for a specific service
docker-compose logs -f <service-name>
# Example: docker-compose logs -f api-service

# Start specific service
docker-compose up -d <service-name>
# Example: docker-compose up -d api-service

# Rebuild and restart services after code changes
docker-compose up -d --build

# Stop all services
docker-compose down
```

### Development Workflow

```bash
# Run database only (useful for developing other services locally)
docker-compose up -d db

# Add a single document for processing
cp your-document.pdf ./data/

# Bulk import documents from Zotero
./scripts/import_documents.sh /home/mu/Zotero/storage

# Advanced import with metadata
python ./scripts/import_with_metadata.py /home/mu/Zotero/storage

# Import with OCR support (for scanned documents)
python ./scripts/import_with_ocr.py /home/mu/Zotero/storage

# Process a specific file
curl -X POST http://localhost:8000/process-file -H "Content-Type: application/json" -d '{"file_path": "/app/data/document.pdf"}'

# Restart a specific service (useful after code changes)
./scripts/restart_service.sh graphrag-processor --build

# View available services and restart options
./scripts/restart_service.sh --help

# Trigger reprocessing of documents via API
curl -X POST http://localhost:5050/trigger-ingestion

# Check ingestion status
curl http://localhost:5050/status

# Check API health
curl http://localhost:8000/health

# View ingestion progress
curl http://localhost:8000/ingestion/progress

# View memory statistics
curl http://localhost:8000/memory/stats

# Clear the system's memory
curl -X DELETE http://localhost:8000/memory/clear

# List favorite queries
curl http://localhost:8000/favorites

# List all conversation threads
curl http://localhost:8000/threads

# Run API service directly (for development)
cd api_service
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Run frontend development server
cd frontend
npm install
npm run dev

# Test QA system
python test_enhanced_qa_system.py  # Run full test suite
python run_enhanced_qa_tests.py security  # Run specific test

# Query the system
curl -X POST http://localhost:8000/query -H "Content-Type: application/json" -d '{"query": "Your question here", "use_amplification": true}'

# Simple queries (faster, legacy endpoint)
curl -X POST http://localhost:8000/query/simple -H "Content-Type: application/json" -d '{"query": "Your question here"}'

# Backup the database
./scripts/backup_db.sh [optional_backup_directory]

# Restore from a backup
./scripts/restore_db.sh path/to/backup.sql.gz

# Set up scheduled backups with retention
./scripts/scheduled_backup.sh [backup_directory] [retention_count]

# MCP Server operations
# Connect to MCP server for programmatic access
docker compose exec -T mcp-server python /app/mcp_server/server.py
```

## Architecture

The application consists of seven containerized services:

1. **db** - PostgreSQL with pgvector
   - Stores document chunks in `document_chunks` table
   - Stores embeddings in `chunk_embeddings` table
   - Stores query memory in `query_cache` table
   - Stores user feedback and threads in `user_feedback` and `thread_messages` tables
   - Enables vector similarity search

2. **ingestion-service**
   - Watches for new documents in the `data` directory
   - Processes documents into chunks
   - Generates embeddings using OpenAI API
   - Stores chunks and embeddings in the database
   - Processes PDF, DOCX, TXT files
   - Handles OCR for scanned documents and images
   - Exposes `/process-file` endpoint for single file processing

3. **graphrag-processor**
   - Builds a knowledge graph from document chunks
   - Extracts entities using spaCy
   - Creates entity relationships
   - Identifies communities in the graph
   - Generates summaries for entity communities
   - Saves graph data to a shared volume

4. **api-service**
   - FastAPI backend
   - Processes user queries
   - Performs vector similarity search
   - Enhances retrieval with graph data
   - Generates answers with OpenAI
   - Remembers past queries for faster responses
   - Supports user feedback and favorites
   - Manages conversation threads with document-grounded dialog
   - Exposes `/query` endpoint for the frontend

5. **frontend**
   - Vue.js SPA
   - User interface for submitting queries
   - Displays answers with citations
   - Shows relevant chunks
   - Allows users to provide feedback and favorite queries
   - Supports creating conversation threads from interesting queries
   - Provides dialog capability with optional retrieval enhancement

6. **ocr-service**
   - Dedicated OCR processing service
   - Handles scanned PDFs and images
   - Converts documents to searchable PDFs
   - Works with the ingestion service

7. **mcp-server**
   - Model Context Protocol server
   - Exposes Consilience functionality via MCP
   - Provides programmatic access to query and ingestion
   - Integrates with Claude Desktop and other MCP clients

6. **ocr-service**
   - Dedicated OCR processing service
   - Handles scanned PDFs and images
   - Converts documents to searchable PDFs
   - Works with the ingestion service

## Data Flow

1. Documents are added to the `data` directory
2. Ingestion service processes documents into chunks and generates embeddings
3. GraphRAG processor builds a knowledge graph from the chunks and embeddings
4. User submits a query through the frontend
5. API service processes the query:
   - Checks memory for matching or semantically similar queries
   - If found in memory, returns remembered result
   - If not found in memory:
     - Embeds the query
     - Finds relevant chunks through vector similarity
     - Enhances retrieval with graph data
     - Generates an answer with citations
     - Stores result in memory for future queries
6. Frontend displays the result to the user
7. User can provide feedback, favorite the query, or create a conversation thread
8. In conversation threads, users can continue the dialog with options for document-grounded responses

## Key Files and Components

### API Service (`api_service/app.py`)
- Main API routes in FastAPI
- Query processing and answer generation
- Vector search and graph-enhanced retrieval
- Memory management
- Feedback and favorites functionality
- Thread management and dialog capability
- Health and status endpoints
- `/process-file` endpoint for single file processing

### Database Schema
- `document_chunks` table - Stores text chunks and metadata
- `chunk_embeddings` table - Stores vector embeddings with pgvector
- `query_cache` table - Stores remembered query results
- `user_feedback` table - Stores user feedback, favorites, and thread metadata
- `thread_messages` table - Stores conversation messages for threads

### Ingestion Service (`ingestion_service/app.py`)
- Document processing pipeline
- File watching and event handling
- Chunk generation and embedding
- OCR processing for scanned documents
- Queue-based parallel processing

### GraphRAG Processor (`graphrag_processor/app.py`)
- Knowledge graph construction
- Entity extraction with spaCy
- Community detection
- Summary generation for entity clusters

### Import Scripts
- `scripts/import_documents.sh` - Basic document importer
- `scripts/import_with_metadata.py` - Advanced import with metadata
- `scripts/import_with_ocr.py` - OCR-enabled import

## Configuration

The system is configured through environment variables:

- `OPENAI_API_KEY` - Required for embeddings and answer generation
- `CHUNK_SIZE` - Size of document chunks (default: 512)
- `CHUNK_OVERLAP` - Overlap between chunks (default: 50)
- `PROCESSING_INTERVAL` - How often the GraphRAG processor runs (default: 3600 seconds)
- `MAX_WORKERS` - Number of parallel workers for ingestion (default: 4)
- `ENABLE_MEMORY` - Enable/disable query memory (default: true)
- `MEMORY_SIMILARITY_THRESHOLD` - Threshold for semantic memory matches (default: 0.95)
- `ENABLE_DIALOG_RETRIEVAL` - Enable/disable retrieval enhancement in dialog threads (default: true)

Important ports:
- Frontend: 8080
- API: 8000
- Ingestion Service: 5050
- PostgreSQL: 5433 (exposed to host, 5432 internally)
- OCR Service: 1337
- MCP Server: stdio (runs within container)

These can be set in a `.env` file at the project root. See `env.example` for a template.

## Technical Notes

- Vector embeddings use OpenAI's `text-embedding-ada-002` model
- Entity extraction uses spaCy's `en_core_web_sm` model
- Answer generation uses OpenAI's `gpt-4o` model
- The knowledge graph is built using networkx
- The frontend is built with Vue 3 Composition API
- OCR processing uses Tesseract and OCRmyPDF
- Handles scanned PDFs and image files through OCR
- Deduplication is performed based on content hashes
- Query memory supports both exact matches and semantic similarity
- Thread dialog can be enhanced with document retrieval

## Common Development Tasks

### Adding New Document Types
To add support for a new document type:
1. Add file extension detection in `ingestion_service/app.py`
2. Implement a custom processor function for the new file type
3. Update the file watching logic to include the new extension

### Customizing Entity Extraction
To modify entity extraction:
1. Adjust the `extract_entities` function in `graphrag_processor/app.py`
2. Consider using a different spaCy model for better entity recognition

### Modifying Answer Generation
To customize how answers are generated:
1. Update the `generate_answer` function in `api_service/app.py`
2. Adjust the prompt template to change answer style or format
3. Consider modifying the model parameters or switching to a different model

### Memory and Feedback Management
To modify the memory and feedback behavior:
1. Adjust the memory-related environment variables
2. Modify the `check_memory` and `save_to_memory` functions in `api_service/app.py`
3. Add additional fields to the feedback schema if needed

### Thread Management
To customize conversation threads:
1. Modify the `generate_thread_message` function in `api_service/app.py`
2. Adjust the thread creation and message handling logic
3. Change the retrieval enhancement parameters