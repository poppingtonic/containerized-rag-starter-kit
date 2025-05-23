from fastapi import APIRouter, HTTPException
from models import ThreadCreateRequest, ThreadMessageRequest, ThreadResponse
from services import ThreadService

router = APIRouter()
thread_service = ThreadService()

@router.post("/create")
async def create_thread(request: ThreadCreateRequest):
    """Create a new conversation thread from a favorite query."""
    try:
        result = thread_service.create_thread(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("s")
async def get_all_threads():
    """Get all conversation threads."""
    try:
        threads = thread_service.get_all_threads()
        return {
            "status": "success",
            "threads": threads
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{thread_id}", response_model=ThreadResponse)
async def get_thread(thread_id: int):
    """Get a specific thread with all messages."""
    try:
        thread = thread_service.get_thread(thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
        return thread
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/message")
async def add_thread_message(request: ThreadMessageRequest):
    """Add a new message to a thread."""
    try:
        result = thread_service.add_message(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))