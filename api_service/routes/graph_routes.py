from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import os

router = APIRouter()

# Database connection
def get_db_connection():
    return psycopg2.connect(os.environ.get("DATABASE_URL"))

@router.get("/triples")
async def get_triples(
    subject: Optional[str] = Query(None, description="Filter by subject"),
    relation: Optional[str] = Query(None, description="Filter by relation"),
    object: Optional[str] = Query(None, description="Filter by object"),
    source: Optional[str] = Query(None, description="Filter by source file"),
    limit: int = Query(100, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination")
):
    """
    Get entity triples (subject-relation-object) from the knowledge graph.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Check if view exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.views 
                        WHERE table_name = 'entity_triples_view'
                    )
                """)
                if not cursor.fetchone()['exists']:
                    raise HTTPException(status_code=404, detail="Entity triples view not found. Please run the GraphRAG processor first.")
                
                # Build query with filters
                query = "SELECT * FROM entity_triples_view WHERE 1=1"
                params = []
                
                if subject:
                    query += " AND subject ILIKE %s"
                    params.append(f"%{subject}%")
                
                if relation:
                    query += " AND relation ILIKE %s"
                    params.append(f"%{relation}%")
                
                if object:
                    query += " AND object ILIKE %s"
                    params.append(f"%{object}%")
                
                if source:
                    query += " AND source_file ILIKE %s"
                    params.append(f"%{source}%")
                
                query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                
                cursor.execute(query, params)
                triples = cursor.fetchall()
                
                # Get total count for pagination
                count_query = "SELECT COUNT(*) FROM entity_triples_view WHERE 1=1"
                count_params = []
                
                if subject:
                    count_query += " AND subject ILIKE %s"
                    count_params.append(f"%{subject}%")
                
                if relation:
                    count_query += " AND relation ILIKE %s"
                    count_params.append(f"%{relation}%")
                
                if object:
                    count_query += " AND object ILIKE %s"
                    count_params.append(f"%{object}%")
                
                if source:
                    count_query += " AND source_file ILIKE %s"
                    count_params.append(f"%{source}%")
                
                cursor.execute(count_query, count_params)
                total_count = cursor.fetchone()['count']
                
                return {
                    "triples": triples,
                    "total": total_count,
                    "limit": limit,
                    "offset": offset
                }
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/triples/stats")
async def get_triples_stats():
    """
    Get statistics about the entity triples in the knowledge graph.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Check if table exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'entity_triples'
                    )
                """)
                if not cursor.fetchone()['exists']:
                    return {
                        "total_triples": 0,
                        "unique_subjects": 0,
                        "unique_relations": 0,
                        "unique_objects": 0,
                        "top_subjects": [],
                        "top_relations": [],
                        "top_objects": []
                    }
                
                # Get basic stats
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_triples,
                        COUNT(DISTINCT subject) as unique_subjects,
                        COUNT(DISTINCT relation) as unique_relations,
                        COUNT(DISTINCT object) as unique_objects
                    FROM entity_triples
                """)
                stats = cursor.fetchone()
                
                # Get top subjects
                cursor.execute("""
                    SELECT subject, COUNT(*) as count
                    FROM entity_triples
                    GROUP BY subject
                    ORDER BY count DESC
                    LIMIT 10
                """)
                top_subjects = cursor.fetchall()
                
                # Get top relations
                cursor.execute("""
                    SELECT relation, COUNT(*) as count
                    FROM entity_triples
                    GROUP BY relation
                    ORDER BY count DESC
                    LIMIT 10
                """)
                top_relations = cursor.fetchall()
                
                # Get top objects
                cursor.execute("""
                    SELECT object, COUNT(*) as count
                    FROM entity_triples
                    GROUP BY object
                    ORDER BY count DESC
                    LIMIT 10
                """)
                top_objects = cursor.fetchall()
                
                return {
                    **stats,
                    "top_subjects": top_subjects,
                    "top_relations": top_relations,
                    "top_objects": top_objects
                }
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/graph/stats")
async def get_graph_stats():
    """
    Get statistics about the knowledge graph structure.
    """
    try:
        # Read the latest graph reference file
        graph_refs_path = os.path.join(os.environ.get("GRAPH_OUTPUT_PATH", "/app/graph_data"), "latest_refs.json")
        
        if not os.path.exists(graph_refs_path):
            raise HTTPException(status_code=404, detail="Graph data not found. Please run the GraphRAG processor first.")
        
        import json
        with open(graph_refs_path, 'r') as f:
            graph_refs = json.load(f)
        
        return {
            "timestamp": graph_refs.get("timestamp"),
            "total_triples": graph_refs.get("total_triples", 0),
            "total_entities": graph_refs.get("total_entities", 0),
            "total_chunks": graph_refs.get("total_chunks", 0),
            "files": {
                "triples_csv": os.path.basename(graph_refs.get("triples_csv", "")),
                "triples_ttl": os.path.basename(graph_refs.get("triples_ttl", "")),
                "entities_csv": os.path.basename(graph_refs.get("entities_csv", "")),
                "stats": os.path.basename(graph_refs.get("stats", ""))
            }
        }
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Graph data not found. Please run the GraphRAG processor first.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export/{filename}")
async def download_export_file(filename: str):
    """
    Download exported graph files (CSV, TTL, or JSON).
    """
    try:
        import os
        from fastapi.responses import FileResponse
        
        # Validate filename to prevent path traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        # Check if file exists
        file_path = os.path.join(os.environ.get("GRAPH_OUTPUT_PATH", "/app/graph_data"), filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        # Determine media type based on extension
        if filename.endswith('.csv'):
            media_type = 'text/csv'
        elif filename.endswith('.ttl'):
            media_type = 'text/turtle'
        elif filename.endswith('.json'):
            media_type = 'application/json'
        else:
            media_type = 'application/octet-stream'
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type=media_type
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))