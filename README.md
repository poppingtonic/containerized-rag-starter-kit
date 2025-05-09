# GraphRAG Query System

A containerized application that generates paragraph answers with references based on user queries, powered by GraphRAG technology.

## Overview

This project implements a full-stack RAG (Retrieval-Augmented Generation) system enhanced with graph-based knowledge representation. The system processes documents, builds a knowledge graph of entities and their relationships, and provides comprehensive answers to user queries with proper citations.

### Key Features

- Document ingestion and chunking
- Vector embeddings with OpenAI
- Entity extraction and relationship mapping
- Knowledge graph construction
- GraphRAG-enhanced retrieval
- Paragraph generation with citations
- Interactive web interface

## Architecture

The application is fully containerized using Docker and consists of the following components:

### 1. Database (PostgreSQL with pgvector)
- Stores document chunks and their embeddings
- Enables vector similarity search

### 2. Ingestion Service
- Processes documents (PDF, DOCX, TXT)
- Chunks documents and generates embeddings
- Stores data in PostgreSQL

### 3. GraphRAG Processor
- Builds a knowledge graph from document chunks
- Extracts entities and relationships
- Generates community summaries
- Outputs graph data for enhanced retrieval

### 4. API Service
- Processes user queries
- Performs vector similarity search
- Enhances retrieval with graph data
- Generates comprehensive answers

### 5. Frontend
- Provides a user-friendly interface
- Displays answers with citations
- Shows relevant chunks, entities, and community insights

## Getting Started

### Prerequisites

- Docker and Docker Compose
- OpenAI API key

### Installation

1. Clone this repository:
   ```
   git clone <repository-url>
   cd writehere-graphrag
   ```

2. Create a `.env` file in the root directory with your OpenAI API key:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```

3. Build and start the containers:
   ```
   docker-compose up -d
   ```

4. The application will be available at:
   - Frontend: http://localhost:8080
   - API: http://localhost:8000
   - Database: localhost:5433 (PostgreSQL)

## Usage

### Adding Documents

#### Manual Addition
1. Place your documents (PDF, DOCX, TXT, images) in the `data` directory
2. The ingestion service will automatically process them
3. The GraphRAG processor will build the knowledge graph

> **Note:** The system supports scanned PDFs and images through OCR processing

#### Bulk Import from Zotero
The project includes two scripts for importing documents in bulk from Zotero storage:

##### Basic Import
1. Run the basic import script:
   ```
   ./scripts/import_documents.sh /home/mu/Zotero/storage
   ```
   
2. The script will:
   - Find all PDF, DOCX, and TXT files in the Zotero storage directory and its subdirectories
   - Copy them to the `data` directory (skipping any duplicates by filename)
   - Report how many new documents were added

##### Advanced Import with Metadata
For a more sophisticated import that preserves folder structure information:

1. Run the advanced import script:
   ```
   ./scripts/import_with_metadata.py /home/mu/Zotero/storage
   ```
   
2. The advanced script offers additional features:
   - Content-based deduplication (using file hashes)
   - Preserves source folder information in filenames
   - Creates a JSON metadata file with original paths and other information
   - Provides more options (run with `--help` to see all options)

   Additional options:
   ```
   # Preserve directory structure in target
   ./scripts/import_with_metadata.py --preserve-structure
   
   # Specify a custom target directory
   ./scripts/import_with_metadata.py --target-dir ./custom_data_dir
   ```

##### Import with OCR Support
For handling scanned documents and images:

1. Run the OCR-enabled import script:
   ```
   ./scripts/import_with_ocr.py /home/mu/Zotero/storage
   ```
   
2. This script provides all the features of the metadata script plus:
   - Automatic detection of scanned PDFs and images
   - OCR processing to make non-searchable documents searchable
   - Parallel processing for faster imports
   - Integration with the OCR service

   Additional options:
   ```
   # Force OCR processing for all documents
   ./scripts/import_with_ocr.py --force-ocr
   
   # Disable OCR processing
   ./scripts/import_with_ocr.py --no-ocr
   
   # Adjust processing threads
   ./scripts/import_with_ocr.py --threads 8
   ```

3. The ingestion service will automatically process the imported documents

> **OCR Note:** The system includes two OCR solutions:
> - Built-in OCR in the ingestion service for direct processing
> - Dedicated OCR service for more advanced preprocessing during import

### Querying

1. Open the frontend at http://localhost:8080
2. Enter your query in the search box
3. View the generated answer with citations
4. Explore the relevant chunks, entities, and community insights

## Technical Details

### Vector Storage and Search

The system uses PostgreSQL with the pgvector extension to store and search vector embeddings, enabling efficient similarity search for relevant document chunks.

### Knowledge Graph Construction

The GraphRAG processor extracts entities from document chunks using spaCy and builds a knowledge graph representing relationships between entities and chunks.

### Query Processing

When a user submits a query:

1. The query is embedded using OpenAI
2. Relevant chunks are retrieved using vector search
3. The knowledge graph is queried for related entities and communities
4. A comprehensive answer is generated with citations

## Development

### Project Structure

```
writehere-graphrag/
├── data/                  # Document storage directory
├── db/                    # Database configuration
├── ingestion_service/     # Document processing service
├── graphrag_processor/    # Knowledge graph generator
├── api_service/           # Query processing API
├── frontend/              # Vue.js web interface
└── docker-compose.yml     # Container orchestration
```

### Customization

- Modify the chunking parameters in `ingestion_service/app.py`
- Adjust the graph processing interval in `graphrag_processor/app.py`
- Change the UI appearance in `frontend/src/assets/main.css`

## License

[MIT License](LICENSE)