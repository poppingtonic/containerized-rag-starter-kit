import json
import time
from fastapi import APIRouter, HTTPException
from services import MemoryService
from utils import get_db_connection

router = APIRouter()
memory_service = MemoryService()

@router.get("/stats")
async def get_memory_stats():
    """Get memory usage statistics."""
    try:
        stats = memory_service.get_memory_stats()
        return {
            "status": "success",
            **stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/clear")
async def clear_memory():
    """Clear all remembered queries."""
    try:
        result = memory_service.clear_memory()
        return {
            "status": "success",
            "message": f"Cleared {result['deleted_entries']} memory entries",
            **result,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/entry/{entry_id}")
async def get_memory_entry(entry_id: int):
    """Get a specific memory entry."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM query_cache WHERE id = %s
                """, (entry_id,))
                
                entry = cursor.fetchone()
                if not entry:
                    raise HTTPException(status_code=404, detail=f"Memory entry {entry_id} not found")
                
                return {
                    "status": "success",
                    "entry": {
                        "id": entry["id"],
                        "query": entry["query"],
                        "answer": entry["answer"],
                        "references": json.loads(entry["references"]) if entry["references"] else [],
                        "chunks": json.loads(entry["chunks"]) if entry["chunks"] else [],
                        "entities": json.loads(entry["entities"]) if entry["entities"] else [],
                        "communities": json.loads(entry["communities"]) if entry["communities"] else [],
                        "created_at": entry["created_at"].isoformat() if entry["created_at"] else None,
                        "access_count": entry["access_count"],
                        "last_accessed": entry["last_accessed"].isoformat() if entry["last_accessed"] else None
                    }
                }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/entry/{entry_id}")
async def delete_memory_entry(entry_id: int):
    """Delete a specific remembered query."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM query_cache WHERE id = %s RETURNING id", (entry_id,))
                deleted = cursor.fetchone()
                conn.commit()
                
                if not deleted:
                    raise HTTPException(status_code=404, detail=f"Memory entry {entry_id} not found")
                
                return {
                    "status": "success",
                    "message": f"Memory entry {entry_id} deleted successfully",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))