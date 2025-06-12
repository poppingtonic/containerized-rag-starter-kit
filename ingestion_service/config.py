"""Configuration settings for the ingestion service."""

import os

# Database configuration
DB_URL = os.environ.get("DATABASE_URL")

# OpenAI configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Directory and file configuration
DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
STATE_FILE = os.environ.get("STATE_FILE", "/app/processed_files.json")
ERROR_LOG = os.environ.get("ERROR_LOG", "/app/error_log.json")

# Processing configuration
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "512"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "50"))
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "4"))
RATE_LIMIT_DELAY = float(os.environ.get("RATE_LIMIT_DELAY", "0.5"))

# Supported file extensions
SUPPORTED_EXTENSIONS = ('.pdf', '.docx', '.txt', '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif')
GLOB_PATTERNS = ['*.pdf', '*.docx', '*.txt', '*.jpg', '*.jpeg', '*.png', '*.tiff', '*.tif', '*.bmp', '*.gif']

# Processing batch sizes
FILE_BATCH_SIZE = 1000
QUEUE_BATCH_SIZE = 100