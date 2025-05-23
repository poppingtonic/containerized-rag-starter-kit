import requests
import time
from fastapi import APIRouter, HTTPException
from utils import get_db_connection

router = APIRouter()

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check database connection
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        
        return {
            "status": "healthy",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "services": {
                "database": "connected",
                "api": "running"
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "error": str(e)
        }

@router.get("/ingestion/progress")
async def get_ingestion_progress():
    """Get the current ingestion progress from the database."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Get overall stats
                cursor.execute("""
                    SELECT 
                        COUNT(DISTINCT source_metadata->>'source') as unique_documents,
                        COUNT(*) as total_chunks
                    FROM document_chunks
                """)
                overall_stats = cursor.fetchone()
                
                # Get embedding stats
                cursor.execute("""
                    SELECT 
                        COUNT(DISTINCT dc.id) as total_chunks,
                        COUNT(DISTINCT ce.chunk_id) as chunks_with_embeddings
                    FROM document_chunks dc
                    LEFT JOIN chunk_embeddings ce ON dc.id = ce.chunk_id
                """)
                embedding_stats = cursor.fetchone()
                
                # Calculate completion percentage
                completion_pct = 0
                if embedding_stats['total_chunks'] > 0:
                    completion_pct = round((embedding_stats['chunks_with_embeddings'] / embedding_stats['total_chunks']) * 100, 1)
                
                # Get OCR stats
                cursor.execute("""
                    SELECT COUNT(DISTINCT source_metadata->>'source') as documents_with_ocr
                    FROM document_chunks
                    WHERE source_metadata->>'ocr_applied' = 'true'
                """)
                ocr_stats = cursor.fetchone()
                
                # Get recent documents
                cursor.execute("""
                    SELECT 
                        source_metadata->>'source' AS document,
                        MIN(created_at) as processed_at,
                        COUNT(*) as chunk_count,
                        MAX(source_metadata->>'ocr_applied') as ocr_applied
                    FROM document_chunks
                    GROUP BY source_metadata->>'source'
                    ORDER BY MIN(created_at) DESC
                    LIMIT 10
                """)
                recent_docs = cursor.fetchall()
                
                # Get document types
                cursor.execute("""
                    SELECT 
                        LOWER(SUBSTRING(source_metadata->>'source' FROM '\.[^.]+$')) as file_type,
                        COUNT(DISTINCT source_metadata->>'source') as document_count
                    FROM document_chunks
                    WHERE source_metadata->>'source' LIKE '%.%'
                    GROUP BY file_type
                    ORDER BY document_count DESC
                """)
                doc_types = cursor.fetchall()
                
                return {
                    "overall": {
                        "unique_documents": overall_stats["unique_documents"] or 0,
                        "total_chunks": overall_stats["total_chunks"] or 0
                    },
                    "embeddings": {
                        "total_chunks": embedding_stats["total_chunks"] or 0,
                        "chunks_with_embeddings": embedding_stats["chunks_with_embeddings"] or 0,
                        "completion_percentage": completion_pct
                    },
                    "ocr": {
                        "documents_with_ocr": ocr_stats["documents_with_ocr"] or 0
                    },
                    "recent_documents": [
                        {
                            "document": doc["document"] or "Unknown",
                            "processed_at": doc["processed_at"].isoformat() if doc["processed_at"] else None,
                            "chunk_count": doc["chunk_count"],
                            "ocr_applied": doc["ocr_applied"] or "false"
                        }
                        for doc in recent_docs
                    ],
                    "document_types": [
                        {
                            "file_type": dtype["file_type"] or "unknown",
                            "document_count": dtype["document_count"]
                        }
                        for dtype in doc_types
                    ]
                }
    except Exception as e:
        # Return a default response on error
        return {
            "overall": {"unique_documents": 0, "total_chunks": 0},
            "embeddings": {"total_chunks": 0, "chunks_with_embeddings": 0, "completion_percentage": 0},
            "ocr": {"documents_with_ocr": 0},
            "recent_documents": [],
            "document_types": [],
            "error": f"Database error: {str(e)}"
        }

@router.post("/ingestion/trigger")
async def trigger_ingestion():
    """Manually trigger document ingestion."""
    try:
        response = requests.post("http://ingestion-service:5050/trigger-ingestion", timeout=5)
        if response.status_code != 200:
            raise HTTPException(status_code=503, detail=f"Ingestion service returned status {response.status_code}")
        
        try:
            return response.json()
        except ValueError:
            return {
                "status": "error",
                "message": "Ingestion service not returning valid JSON"
            }
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Ingestion service unavailable: {str(e)}")