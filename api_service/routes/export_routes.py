import json
import time
import io
import csv
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
from utils import get_db_connection

router = APIRouter()

@router.get("/training-data")
async def export_training_data(
    format: str = Query("jsonl", description="Export format: jsonl, csv, or json"),
    min_rating: Optional[int] = Query(None, description="Minimum rating to include"),
    only_favorites: bool = Query(False, description="Only export favorites"),
    include_chunks: bool = Query(True, description="Include retrieved chunks")
):
    """Export cache entries with feedback for training purposes."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Build query based on filters
                query = """
                    SELECT 
                        qc.id,
                        qc.query_text,
                        qc.answer_text,
                        qc.references,
                        qc.chunks,
                        qc.entities,
                        qc.communities,
                        qc.created_at,
                        qc.ragas_scores,
                        uf.feedback_text,
                        uf.rating,
                        uf.is_favorite
                    FROM query_cache qc
                    INNER JOIN user_feedback uf ON qc.id = uf.query_cache_id
                    WHERE 1=1
                """
                params = []
                
                if min_rating is not None:
                    query += " AND uf.rating >= %s"
                    params.append(min_rating)
                
                if only_favorites:
                    query += " AND uf.is_favorite = true"
                
                query += " ORDER BY qc.created_at DESC"
                
                cursor.execute(query, params)
                entries = cursor.fetchall()
                
                # Format data for export
                export_data = []
                for entry in entries:
                    record = {
                        "id": entry["id"],
                        "query": entry["query_text"],
                        "answer": entry["answer_text"],
                        "references": json.loads(entry["references"]) if entry["references"] else [],
                        "rating": entry["rating"],
                        "is_favorite": entry["is_favorite"],
                        "feedback": entry["feedback_text"],
                        "created_at": entry["created_at"].isoformat() if entry["created_at"] else None
                    }
                    
                    # Add RAGAS scores if available
                    if entry["ragas_scores"]:
                        record["ragas_scores"] = json.loads(entry["ragas_scores"]) if isinstance(entry["ragas_scores"], str) else entry["ragas_scores"]
                    
                    if include_chunks:
                        record["chunks"] = json.loads(entry["chunks"]) if entry["chunks"] else []
                        record["entities"] = json.loads(entry["entities"]) if entry["entities"] else []
                        record["communities"] = json.loads(entry["communities"]) if entry["communities"] else []
                    
                    export_data.append(record)
                
                # Format based on requested format
                if format == "jsonl":
                    buffer = io.StringIO()
                    for record in export_data:
                        buffer.write(json.dumps(record) + "\n")
                    buffer.seek(0)
                    
                    return StreamingResponse(
                        buffer,
                        media_type="application/x-jsonlines",
                        headers={
                            "Content-Disposition": f"attachment; filename=training_data_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
                        }
                    )
                
                elif format == "csv":
                    buffer = io.StringIO()
                    if export_data:
                        # Flatten data for CSV
                        flat_data = []
                        for record in export_data:
                            flat_record = {
                                "id": record["id"],
                                "query": record["query"],
                                "answer": record["answer"],
                                "references": "; ".join(record["references"]),
                                "rating": record["rating"],
                                "is_favorite": record["is_favorite"],
                                "feedback": record["feedback"],
                                "created_at": record["created_at"]
                            }
                            if include_chunks:
                                flat_record["num_chunks"] = len(record.get("chunks", []))
                                flat_record["num_entities"] = len(record.get("entities", []))
                            flat_data.append(flat_record)
                        
                        writer = csv.DictWriter(buffer, fieldnames=flat_data[0].keys())
                        writer.writeheader()
                        writer.writerows(flat_data)
                    
                    buffer.seek(0)
                    
                    return StreamingResponse(
                        buffer,
                        media_type="text/csv",
                        headers={
                            "Content-Disposition": f"attachment; filename=training_data_{time.strftime('%Y%m%d_%H%M%S')}.csv"
                        }
                    )
                
                else:  # json
                    return {
                        "status": "success",
                        "count": len(export_data),
                        "data": export_data
                    }
                    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/evaluation-report")
async def export_evaluation_report():
    """Generate a comprehensive evaluation report."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Get queries with feedback
                cursor.execute("""
                    SELECT 
                        qc.query_text,
                        qc.answer_text,
                        LENGTH(qc.answer_text) as answer_length,
                        json_array_length(qc.references::json) as num_references,
                        json_array_length(qc.chunks::json) as num_chunks,
                        uf.rating,
                        uf.feedback_text,
                        uf.is_favorite
                    FROM query_cache qc
                    INNER JOIN user_feedback uf ON qc.id = uf.query_cache_id
                    WHERE uf.rating IS NOT NULL
                """)
                evaluated_queries = cursor.fetchall()
                
                if not evaluated_queries:
                    return {
                        "status": "success",
                        "report": {
                            "summary": "No evaluated queries found",
                            "details": {}
                        }
                    }
                
                # Calculate metrics
                ratings = [q["rating"] for q in evaluated_queries]
                avg_rating = sum(ratings) / len(ratings)
                
                # Rating breakdown
                rating_counts = {i: ratings.count(i) for i in range(1, 6)}
                
                # Answer characteristics by rating
                rating_groups = {}
                for rating in range(1, 6):
                    group_queries = [q for q in evaluated_queries if q["rating"] == rating]
                    if group_queries:
                        rating_groups[rating] = {
                            "count": len(group_queries),
                            "avg_answer_length": sum(q["answer_length"] for q in group_queries) / len(group_queries),
                            "avg_references": sum(q["num_references"] for q in group_queries) / len(group_queries),
                            "avg_chunks": sum(q["num_chunks"] for q in group_queries) / len(group_queries),
                            "favorites_percentage": sum(1 for q in group_queries if q["is_favorite"]) / len(group_queries) * 100
                        }
                
                # Sample feedback by rating
                feedback_samples = {}
                for rating in range(1, 6):
                    samples = [q["feedback_text"] for q in evaluated_queries 
                             if q["rating"] == rating and q["feedback_text"]]
                    feedback_samples[rating] = samples[:3]  # Top 3 samples
                
                report = {
                    "summary": {
                        "total_evaluated": len(evaluated_queries),
                        "average_rating": round(avg_rating, 2),
                        "rating_distribution": rating_counts,
                        "favorites_count": sum(1 for q in evaluated_queries if q["is_favorite"]),
                        "feedback_provided": sum(1 for q in evaluated_queries if q["feedback_text"])
                    },
                    "rating_analysis": rating_groups,
                    "feedback_samples": feedback_samples,
                    "recommendations": []
                }
                
                # Add recommendations based on analysis
                if avg_rating < 3:
                    report["recommendations"].append("Overall rating is low. Consider improving answer generation quality.")
                
                if rating_groups.get(5, {}).get("avg_chunks", 0) > rating_groups.get(1, {}).get("avg_chunks", float('inf')):
                    report["recommendations"].append("Higher-rated answers tend to use more chunks. Consider retrieving more context.")
                
                if sum(1 for q in evaluated_queries if q["num_references"] == 0) > len(evaluated_queries) * 0.2:
                    report["recommendations"].append("Many answers lack references. Ensure citation generation is working properly.")
                
                return {
                    "status": "success",
                    "report": report,
                    "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))