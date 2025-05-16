# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GraphRAG Query System is a containerized application that generates paragraph answers with references based on user queries, powered by GraphRAG technology. The system processes documents, builds a knowledge graph of entities and their relationships, and provides comprehensive answers with citations.

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

# Trigger reprocessing of documents via API
curl -X POST http://localhost:5050/trigger-ingestion

# Check ingestion status
curl http://localhost:5050/status

# Check API health
curl http://localhost:8000/health

# View ingestion progress
curl http://localhost:8000/ingestion/progress

# Run API service directly (for development)
cd api_service
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Run frontend development server
cd frontend
npm install
npm run dev
```

## Architecture

The application consists of five containerized services:

1. **db** - PostgreSQL with pgvector
   - Stores document chunks in `document_chunks` table
   - Stores embeddings in `chunk_embeddings` table
   - Enables vector similarity search

2. **ingestion-service**
   - Watches for new documents in the `data` directory
   - Processes documents into chunks
   - Generates embeddings using OpenAI API
   - Stores chunks and embeddings in the database
   - Processes PDF, DOCX, TXT files
   - Handles OCR for scanned documents and images

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
   - Exposes `/query` endpoint for the frontend

5. **frontend**
   - Vue.js SPA
   - User interface for submitting queries
   - Displays answers with citations
   - Shows relevant chunks, entities, and community insights

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
   - Embeds the query
   - Finds relevant chunks through vector similarity
   - Enhances retrieval with graph data
   - Generates an answer with citations
6. Frontend displays the result to the user

## Key Files and Components

### API Service (`api_service/app.py`)
- Main API routes in FastAPI
- Query processing and answer generation
- Vector search and graph-enhanced retrieval
- Health and status endpoints

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

### Database Schema
- `document_chunks` table - Stores text chunks and metadata
- `chunk_embeddings` table - Stores vector embeddings with pgvector

## Configuration

The system is configured through environment variables:

- `OPENAI_API_KEY` - Required for embeddings and answer generation
- `CHUNK_SIZE` - Size of document chunks (default: 512)
- `CHUNK_OVERLAP` - Overlap between chunks (default: 50)
- `PROCESSING_INTERVAL` - How often the GraphRAG processor runs (default: 3600 seconds)
- `MAX_WORKERS` - Number of parallel workers for ingestion (default: 4)

Important ports:
- Frontend: 8080
- API: 8000
- Ingestion Service: 5050
- PostgreSQL: 5433 (exposed to host, 5432 internally)
- OCR Service: 1337

These can be set in a `.env` file at the project root. See `env.example` for a template.

## Technical Notes

- Vector embeddings use OpenAI's `text-embedding-ada-002` model
- Entity extraction uses spaCy's `en_core_web_sm` model
- Answer generation uses OpenAI's `gpt-3.5-turbo` model
- The knowledge graph is built using networkx
- The frontend is built with Vue 3 Composition API
- OCR processing uses Tesseract and OCRmyPDF
- Handles scanned PDFs and image files through OCR
- Deduplication is performed based on content hashes

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