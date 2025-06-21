import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

class ProcessFileRequest(BaseModel):
    file_path: str

router = APIRouter()

@router.post("/process-file")
async def process_file(request: ProcessFileRequest):
    """Process a specific file."""
    try:
        response = requests.post(
            "http://ingestion-service:5050/process-file",
            json={"file_path": request.file_path},
            timeout=5
        )
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