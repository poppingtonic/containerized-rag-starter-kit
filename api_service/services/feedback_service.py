import json
from typing import List, Dict, Any
from models import FeedbackRequest
from utils import get_db_connection

class FeedbackService:
    def save_feedback(self, feedback: FeedbackRequest) -> Dict[str, Any]:
        """Save user feedback for a query."""
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Check if memory ID exists
                cursor.execute("SELECT id FROM query_cache WHERE id = %s", (feedback.memory_id,))
                if not cursor.fetchone():
                    return {
                        "status": "error",
                        "message": f"Memory entry with ID {feedback.memory_id} not found"
                    }
                
                # Check if feedback already exists
                cursor.execute("SELECT id FROM user_feedback WHERE query_cache_id = %s", (feedback.memory_id,))
                existing_feedback = cursor.fetchone()
                
                if existing_feedback:
                    # Update existing feedback
                    update_parts = []
                    update_values = []
                    
                    if feedback.feedback_text is not None:
                        update_parts.append("feedback_text = %s")
                        update_values.append(feedback.feedback_text)
                        
                    if feedback.rating is not None:
                        update_parts.append("rating = %s")
                        update_values.append(feedback.rating)
                        
                    if feedback.is_favorite is not None:
                        update_parts.append("is_favorite = %s")
                        update_values.append(feedback.is_favorite)
                    
                    update_parts.append("updated_at = CURRENT_TIMESTAMP")
                    
                    if update_parts:
                        query = f"""
                            UPDATE user_feedback 
                            SET {", ".join(update_parts)}
                            WHERE id = %s
                            RETURNING id
                        """
                        update_values.append(existing_feedback['id'])
                        cursor.execute(query, update_values)
                        updated_id = cursor.fetchone()['id']
                        conn.commit()
                        
                        return {
                            "status": "success",
                            "message": "Feedback updated successfully",
                            "id": updated_id
                        }
                else:
                    # Create new feedback
                    cursor.execute("""
                        INSERT INTO user_feedback 
                        (query_cache_id, feedback_text, rating, is_favorite)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id
                    """, (
                        feedback.memory_id,
                        feedback.feedback_text,
                        feedback.rating,
                        feedback.is_favorite if feedback.is_favorite is not None else False
                    ))
                    
                    new_id = cursor.fetchone()['id']
                    conn.commit()
                    
                    return {
                        "status": "success",
                        "message": "Feedback saved successfully",
                        "id": new_id
                    }
    
    def get_favorites(self) -> List[Dict[str, Any]]:
        """Get all favorite queries."""
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        qc.id,
                        qc.query_text,
                        qc.answer_text,
                        qc.references,
                        qc.created_at,
                        uf.rating,
                        uf.feedback_text,
                        uf.created_at as favorited_at
                    FROM query_cache qc
                    INNER JOIN user_feedback uf ON qc.id = uf.query_cache_id
                    WHERE uf.is_favorite = true
                    ORDER BY uf.created_at DESC
                """)
                
                favorites = cursor.fetchall()
                
                return [
                    {
                        "id": fav["id"],
                        "query": fav["query_text"],
                        "answer": fav["answer_text"],
                        "references": json.loads(fav["references"]) if fav["references"] else [],
                        "created_at": fav["created_at"].isoformat() if fav["created_at"] else None,
                        "rating": fav["rating"],
                        "feedback": fav["feedback_text"],
                        "favorited_at": fav["favorited_at"].isoformat() if fav["favorited_at"] else None
                    }
                    for fav in favorites
                ]