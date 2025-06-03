from fastapi import APIRouter, HTTPException
from models import FeedbackRequest
from services import FeedbackService
from utils import get_db_connection

router = APIRouter()

@router.post("/feedback")
async def save_feedback(feedback: FeedbackRequest):
    """Save user feedback for a query."""
    try:
        feedback_service = FeedbackService()
        result = feedback_service.save_feedback(feedback)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/favorites")
async def get_favorites():
    """Get all favorite queries."""
    try:
        feedback_service = FeedbackService()
        favorites = feedback_service.get_favorites()
        return {
            "status": "success",
            "favorites": favorites
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/evaluation/metrics")
async def get_evaluation_metrics():
    """Get aggregated evaluation metrics from user feedback."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Get rating distribution
                cursor.execute("""
                    SELECT 
                        rating,
                        COUNT(*) as count
                    FROM user_feedback
                    WHERE rating IS NOT NULL
                    GROUP BY rating
                    ORDER BY rating
                """)
                rating_distribution = cursor.fetchall()
                
                # Get overall statistics
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_feedback,
                        COUNT(CASE WHEN rating IS NOT NULL THEN 1 END) as rated_count,
                        AVG(rating) as average_rating,
                        COUNT(CASE WHEN is_favorite = true THEN 1 END) as favorites_count,
                        COUNT(CASE WHEN feedback_text IS NOT NULL THEN 1 END) as text_feedback_count
                    FROM user_feedback
                """)
                stats = cursor.fetchone()
                
                # Get feedback by time
                cursor.execute("""
                    SELECT 
                        DATE(created_at) as date,
                        COUNT(*) as feedback_count,
                        AVG(rating) as avg_rating
                    FROM user_feedback
                    WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
                    GROUP BY DATE(created_at)
                    ORDER BY date
                """)
                feedback_timeline = cursor.fetchall()
                
                return {
                    "status": "success",
                    "metrics": {
                        "overall": {
                            "total_feedback": stats["total_feedback"],
                            "rated_count": stats["rated_count"],
                            "average_rating": float(stats["average_rating"]) if stats["average_rating"] else None,
                            "favorites_count": stats["favorites_count"],
                            "text_feedback_count": stats["text_feedback_count"]
                        },
                        "rating_distribution": [
                            {"rating": r["rating"], "count": r["count"]} 
                            for r in rating_distribution
                        ],
                        "timeline": [
                            {
                                "date": t["date"].isoformat(),
                                "feedback_count": t["feedback_count"],
                                "average_rating": float(t["avg_rating"]) if t["avg_rating"] else None
                            }
                            for t in feedback_timeline
                        ]
                    }
                }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))