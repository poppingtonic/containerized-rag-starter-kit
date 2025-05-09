#!/bin/bash

# Script to connect to PostgreSQL and check ingestion progress

# Connection parameters (using the port we configured - 5433)
PG_HOST="localhost"
PG_PORT="5433"
PG_DB="graphragdb"
PG_USER="graphraguser"
PG_PASS="graphragpassword"

# Connect and run queries
echo "Connecting to PostgreSQL to check ingestion progress..."
PGPASSWORD=$PG_PASS psql -h $PG_HOST -p $PG_PORT -d $PG_DB -U $PG_USER << EOF

-- Check how many documents have been processed
SELECT 
    COUNT(*) AS total_chunks,
    COUNT(DISTINCT source_metadata->>'source') AS unique_documents
FROM document_chunks;

-- Check document processing status (most recent documents)
SELECT 
    source_metadata->>'source' AS document,
    source_metadata->>'processed_at' AS processed_at,
    source_metadata->>'ocr_applied' AS ocr_applied,
    COUNT(*) AS chunk_count
FROM document_chunks
GROUP BY document, processed_at, ocr_applied
ORDER BY processed_at DESC NULLS LAST
LIMIT 10;

-- Check embedding status
SELECT 
    'Total chunks' AS description,
    COUNT(*) AS count 
FROM document_chunks
UNION
SELECT 
    'Chunks with embeddings' AS description,
    COUNT(*) AS count 
FROM chunk_embeddings;

-- Check processing rates (chunks per hour)
SELECT 
    date_trunc('hour', created_at) AS hour,
    COUNT(*) AS chunks_processed
FROM document_chunks
GROUP BY hour
ORDER BY hour DESC
LIMIT 24;

EOF