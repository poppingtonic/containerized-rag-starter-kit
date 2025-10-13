import os
import requests
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional
from utils import Config

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

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a document, save locally, optionally mirror to Azure, and enqueue for ingestion."""
    try:
        # Ensure upload directory exists
        os.makedirs(Config.UPLOAD_DIR, exist_ok=True)

        # Build local save path
        filename = file.filename or "upload.bin"
        safe_filename = os.path.basename(filename)
        local_path = os.path.join(Config.UPLOAD_DIR, safe_filename)

        # Save to local filesystem
        with open(local_path, "wb") as f:
            content = await file.read()
            f.write(content)

        azure_blob_url: Optional[str] = None
        if Config.AZURE_STORAGE_ENABLED and Config.AZURE_STORAGE_CONNECTION_STRING:
            try:
                from azure.storage.blob import BlobServiceClient, ContentSettings

                blob_service_client = BlobServiceClient.from_connection_string(
                    Config.AZURE_STORAGE_CONNECTION_STRING
                )
                container_client = blob_service_client.get_container_client(Config.AZURE_STORAGE_CONTAINER)
                # Create container if not exists
                try:
                    container_client.create_container()
                except Exception:
                    pass

                blob_name = f"{Config.AZURE_STORAGE_PREFIX.rstrip('/')}/{safe_filename}"
                blob_client = container_client.get_blob_client(blob_name)
                content_settings = ContentSettings(content_type=file.content_type or "application/octet-stream")

                # Upload from local content
                with open(local_path, "rb") as data:
                    blob_client.upload_blob(data, overwrite=True, content_settings=content_settings)
                try:
                    azure_blob_url = blob_client.url
                except Exception:
                    azure_blob_url = None
            except Exception as az_err:
                # Log but do not fail the upload if Azure upload fails
                azure_blob_url = None
                print(f"Azure upload failed: {az_err}")

        # Trigger ingestion on the local file path (shared volume expected between services)
        try:
            response = requests.post(
                "http://ingestion-service:5050/process-file",
                json={"file_path": local_path},
                timeout=10,
            )
            ingestion_resp = response.json() if response.headers.get("Content-Type", "").startswith("application/json") else {
                "status": "unknown",
                "raw": response.text,
            }
        except Exception as e:
            ingestion_resp = {"status": "error", "message": f"Failed to call ingestion service: {e}"}

        return {
            "status": "success",
            "filename": safe_filename,
            "local_path": local_path,
            "azure_blob_url": azure_blob_url,
            "ingestion": ingestion_resp,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")