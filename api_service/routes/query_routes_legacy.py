from fastapi import APIRouter, HTTPException
from models import Query, FullResponse
from services import QueryService

router = APIRouter()
query_service = QueryService()

@router.post("/query", response_model=FullResponse)
async def process_query(query_data: Query):
    """Process a user query and return comprehensive results."""
    try:
        response = await query_service.process_query(
            query_data.query, 
            query_data.max_results, 
            query_data.use_memory
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))