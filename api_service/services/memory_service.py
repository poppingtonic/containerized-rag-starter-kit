import json
import numpy as np
from typing import List, Dict, Any, Optional
from utils import get_db_connection, Config

class MemoryService:
    def check_memory(self, query: str, query_embedding: List[float]) -> Optional[Dict[str, Any]]:
        """Check if query exists in memory."""
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Check for exact match
                cursor.execute("""
                    SELECT id, answer_text as answer, "references", chunk_ids as chunks, entities, communities
                    FROM query_cache
                    WHERE LOWER(query_text) = LOWER(%s)
                """, (query,))
                
                exact_match = cursor.fetchone()
                if exact_match:
                    # Update access count and timestamp
                    cursor.execute("""
                        UPDATE query_cache 
                        SET access_count = access_count + 1, 
                            last_accessed = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (exact_match['id'],))
                    conn.commit()
                    
                    return self._format_memory_response(exact_match, query)
                
                # Check for semantic similarity
                embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
                cursor.execute("""
                    SELECT id, query_text as query, answer_text as answer, "references", chunk_ids as chunks, entities, communities,
                           1 - (query_embedding <=> %s::vector) as similarity
                    FROM query_cache
                    WHERE 1 - (query_embedding <=> %s::vector) > %s
                    ORDER BY query_embedding <=> %s::vector
                    LIMIT 1
                """, (embedding_str, embedding_str, Config.MEMORY_SIMILARITY_THRESHOLD, embedding_str))
                
                similar_match = cursor.fetchone()
                if similar_match:
                    # Update access count and timestamp
                    cursor.execute("""
                        UPDATE query_cache 
                        SET access_count = access_count + 1, 
                            last_accessed = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (similar_match['id'],))
                    conn.commit()
                    
                    return self._format_memory_response(similar_match, query)
                
                return None
    
    def _format_memory_response(self, cache_entry: Dict, query: str) -> Dict[str, Any]:
        """Format a memory cache entry into a response."""
        # Parse stored data (jsonb columns return objects directly, not strings)
        chunks = cache_entry['chunks'] if cache_entry['chunks'] else []
        entities = cache_entry['entities'] if cache_entry['entities'] else []
        communities = cache_entry['communities'] if cache_entry['communities'] else []
        references = cache_entry['references'] if cache_entry['references'] else []
        
        # Fetch full chunk data for each chunk ID
        formatted_chunks = []
        if chunks:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    for chunk_id in chunks:
                        cursor.execute("""
                            SELECT 
                                dc.id, 
                                dc.text_content, 
                                dc.source_metadata
                            FROM 
                                document_chunks dc
                            WHERE 
                                dc.id = %s
                        """, (chunk_id,))
                        
                        chunk = cursor.fetchone()
                        if chunk:
                            # Handle source_metadata (jsonb column returns dict, not string)
                            if isinstance(chunk["source_metadata"], str):
                                metadata = json.loads(chunk["source_metadata"])
                            else:
                                metadata = chunk["source_metadata"]
                            
                            formatted_chunks.append({
                                "id": chunk["id"],
                                "text": chunk["text_content"],
                                "source": metadata.get("source", "Unknown source"),
                                "similarity": 1.0  # Set to 1.0 for remembered results
                            })
        
        return {
            "query": query,
            "answer": cache_entry['answer'],
            "chunks": formatted_chunks,
            "entities": entities,
            "communities": communities,
            "references": references,
            "from_memory": True,
            "memory_id": cache_entry['id']
        }
    
    def save_to_memory(self, query: str, query_embedding: List[float], answer: str, 
                      references: List[str], chunks: List[Dict], entities: List[Dict], 
                      communities: List[Dict]) -> Optional[int]:
        """Save query result to memory cache."""
        if not Config.ENABLE_MEMORY:
            return None
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Prepare data for storage
                    chunk_ids = [chunk['id'] for chunk in chunks]
                    embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
                    
                    cursor.execute("""
                        INSERT INTO query_cache 
                        (query_text, query_embedding, answer_text, "references", chunk_ids, entities, communities)
                        VALUES (%s, %s::vector, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        query,
                        embedding_str,
                        answer,
                        json.dumps(references),
                        json.dumps(chunk_ids),
                        json.dumps(entities),
                        json.dumps(communities)
                    ))
                    
                    memory_id = cursor.fetchone()['id']
                    conn.commit()
                    return memory_id
        except Exception as e:
            print(f"Error saving to memory: {e}")
            return None
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Get overall statistics
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_entries,
                        SUM(access_count) as total_accesses,
                        AVG(access_count) as avg_accesses,
                        MAX(access_count) as max_accesses,
                        MIN(created_at) as oldest_entry,
                        MAX(created_at) as newest_entry
                    FROM query_cache
                """)
                stats = cursor.fetchone()
                
                # Get most accessed queries
                cursor.execute("""
                    SELECT query_text as query, access_count, created_at, last_accessed
                    FROM query_cache
                    ORDER BY access_count DESC
                    LIMIT 10
                """)
                most_accessed = cursor.fetchall()
                
                # Get recent queries
                cursor.execute("""
                    SELECT query_text as query, access_count, created_at
                    FROM query_cache
                    ORDER BY created_at DESC
                    LIMIT 10
                """)
                recent_queries = cursor.fetchall()
                
                return {
                    "total_entries": stats["total_entries"] or 0,
                    "total_accesses": stats["total_accesses"] or 0,
                    "average_accesses": float(stats["avg_accesses"]) if stats["avg_accesses"] else 0,
                    "max_accesses": stats["max_accesses"] or 0,
                    "oldest_entry": stats["oldest_entry"].isoformat() if stats["oldest_entry"] else None,
                    "newest_entry": stats["newest_entry"].isoformat() if stats["newest_entry"] else None,
                    "most_accessed": [
                        {
                            "query": q["query"],
                            "access_count": q["access_count"],
                            "created_at": q["created_at"].isoformat() if q["created_at"] else None,
                            "last_accessed": q["last_accessed"].isoformat() if q["last_accessed"] else None
                        } for q in most_accessed
                    ],
                    "recent_queries": [
                        {
                            "query": q["query"],
                            "access_count": q["access_count"],
                            "created_at": q["created_at"].isoformat() if q["created_at"] else None
                        } for q in recent_queries
                    ]
                }
    
    def clear_memory(self) -> Dict[str, Any]:
        """Clear all memory entries."""
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM query_cache")
                deleted_count = cursor.rowcount
                conn.commit()
                
                return {
                    "deleted_entries": deleted_count
                }