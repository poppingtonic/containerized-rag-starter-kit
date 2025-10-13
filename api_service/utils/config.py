import os
from __future__ import annotations

class Config:
    DB_URL = os.environ.get("DATABASE_URL")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
    GRAPH_OUTPUT_PATH = os.environ.get("GRAPH_OUTPUT_PATH", "/app/graph_data")
    ENABLE_MEMORY = os.environ.get("ENABLE_MEMORY", "true").lower() == "true"
    MEMORY_SIMILARITY_THRESHOLD = float(os.environ.get("MEMORY_SIMILARITY_THRESHOLD", "0.95"))
    ENABLE_DIALOG_RETRIEVAL = os.environ.get("ENABLE_DIALOG_RETRIEVAL", "true").lower() == "true"
    
    # Enhanced QA Configuration
    ENABLE_ENHANCED_QA = os.environ.get("ENABLE_ENHANCED_QA", "true").lower() == "true"
    ENABLE_CHUNK_CLASSIFICATION = os.environ.get("ENABLE_CHUNK_CLASSIFICATION", "true").lower() == "true"
    ENABLE_SUBQUESTION_AMPLIFICATION = os.environ.get("ENABLE_SUBQUESTION_AMPLIFICATION", "false").lower() == "true"
    ENABLE_ANSWER_VERIFICATION = os.environ.get("ENABLE_ANSWER_VERIFICATION", "true").lower() == "true"
    CHUNK_RELEVANCE_THRESHOLD = float(os.environ.get("CHUNK_RELEVANCE_THRESHOLD", "0.5"))
    VERIFICATION_THRESHOLD = float(os.environ.get("VERIFICATION_THRESHOLD", "0.7"))
    MAX_SUBQUESTIONS = int(os.environ.get("MAX_SUBQUESTIONS", "4"))
    AMPLIFICATION_MIN_CONTEXT_LENGTH = int(os.environ.get("AMPLIFICATION_MIN_CONTEXT_LENGTH", "500"))

    # Uploads / Storage
    UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/data/uploads")
    AZURE_STORAGE_ENABLED = os.environ.get("AZURE_STORAGE_ENABLED", "false").lower() == "true"
    AZURE_STORAGE_CONNECTION_STRING = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
    AZURE_STORAGE_CONTAINER = os.environ.get("AZURE_STORAGE_CONTAINER", "documents")
    AZURE_STORAGE_PREFIX = os.environ.get("AZURE_STORAGE_PREFIX", "uploads/")