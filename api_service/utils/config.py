import os

class Config:
    DB_URL = os.environ.get("DATABASE_URL")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    GRAPH_OUTPUT_PATH = os.environ.get("GRAPH_OUTPUT_PATH", "/app/graph_data")
    ENABLE_MEMORY = os.environ.get("ENABLE_MEMORY", "true").lower() == "true"
    MEMORY_SIMILARITY_THRESHOLD = float(os.environ.get("MEMORY_SIMILARITY_THRESHOLD", "0.95"))
    ENABLE_DIALOG_RETRIEVAL = os.environ.get("ENABLE_DIALOG_RETRIEVAL", "true").lower() == "true"