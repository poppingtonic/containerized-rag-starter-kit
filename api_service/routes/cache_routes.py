import json
from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from utils import get_db_connection

router = APIRouter()

@router.get("/entries")
async def get_cache_entries(
    limit: int = Query(50, description="Number of entries to return"),
    offset: int = Query(0, description="Pagination offset"),
    include_feedback: bool = Query(True, description="Include feedback data")
):
    """Get all cache entries with optional feedback data."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Get total count
                cursor.execute("SELECT COUNT(*) as total FROM query_cache")
                total_count = cursor.fetchone()['total']
                
                # Get cache entries with feedback
                query = """
                    SELECT 
                        qc.id,
                        qc.query_text as query,
                        qc.answer_text as answer,
                        qc."references",
                        qc.chunk_ids as chunks,
                        qc.created_at,
                        qc.access_count,
                        qc.last_accessed,
                        uf.feedback_text,
                        uf.rating,
                        uf.is_favorite,
                        uf.created_at as feedback_created_at,
                        uf.updated_at as feedback_updated_at
                    FROM query_cache qc
                    LEFT JOIN user_feedback uf ON qc.id = uf.query_cache_id
                    ORDER BY qc.created_at DESC
                    LIMIT %s OFFSET %s
                """
                
                cursor.execute(query, (limit, offset))
                entries = cursor.fetchall()
                
                formatted_entries = []
                for entry in entries:
                    formatted_entry = {
                        "id": entry["id"],
                        "query": entry["query"],
                        "answer": entry["answer"],
                        "references": entry["references"] if entry["references"] else [],
                        "chunks": entry["chunks"] if entry["chunks"] else [],
                        "created_at": entry["created_at"].isoformat() if entry["created_at"] else None,
                        "access_count": entry["access_count"],
                        "last_accessed": entry["last_accessed"].isoformat() if entry["last_accessed"] else None
                    }
                    
                    if include_feedback:
                        if entry["feedback_text"] is not None or entry["rating"] is not None or entry["is_favorite"] is not None:
                            formatted_entry["feedback"] = {
                                "text": entry["feedback_text"],
                                "rating": entry["rating"],
                                "is_favorite": entry["is_favorite"],
                                "created_at": entry["feedback_created_at"].isoformat() if entry["feedback_created_at"] else None,
                                "updated_at": entry["feedback_updated_at"].isoformat() if entry["feedback_updated_at"] else None
                            }
                        else:
                            formatted_entry["feedback"] = None
                    
                    formatted_entries.append(formatted_entry)
                
                return {
                    "status": "success",
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "entries": formatted_entries
                }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))