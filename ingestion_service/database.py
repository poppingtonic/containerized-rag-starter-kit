"""Database operations for the ingestion service."""

import psycopg2
from psycopg2.extras import execute_values
import json
from .config import DB_URL


def get_db_connection():
    """Get a database connection."""
    return psycopg2.connect(DB_URL)


def check_document_exists(content_hash):
    """Check if a document with the given content hash already exists."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) FROM document_chunks 
                WHERE source_metadata->>'content_hash' = %s
                """, 
                (content_hash,)
            )
            return cursor.fetchone()[0] > 0


def store_chunks_and_embeddings(chunks_data, embeddings_data, metadata):
    """Store document chunks and their embeddings in the database.
    
    Args:
        chunks_data: List of text chunks
        embeddings_data: List of embeddings corresponding to chunks
        metadata: Document metadata dictionary
    
    Returns:
        Number of chunks stored
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # Insert chunks and get IDs
            chunk_ids = []
            for chunk_text in chunks_data:
                # Ensure chunk text is clean
                clean_text = chunk_text.replace('\x00', '')
                # Skip empty chunks
                if not clean_text.strip():
                    continue
                    
                cursor.execute(
                    "INSERT INTO document_chunks (text_content, source_metadata) VALUES (%s, %s) RETURNING id",
                    (clean_text, json.dumps(metadata))
                )
                chunk_id = cursor.fetchone()[0]
                chunk_ids.append(chunk_id)
            
            # Store embeddings if we have any
            if embeddings_data and len(embeddings_data) == len(chunk_ids):
                embedding_values = []
                for chunk_id, embedding in zip(chunk_ids, embeddings_data):
                    # Convert embedding list to pgvector format
                    embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                    embedding_values.append((chunk_id, embedding_str))
                
                execute_values(
                    cursor,
                    "INSERT INTO chunk_embeddings (chunk_id, embedding_vector) VALUES %s",
                    [(chunk_id, f"{emb}") for chunk_id, emb in embedding_values]
                )
            
            conn.commit()
            return len(chunk_ids)