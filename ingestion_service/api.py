"""Flask API for the ingestion service."""

import time
import threading
from datetime import datetime
from flask import Flask, jsonify, request

from .file_discovery import queue_unprocessed_files
from .file_tracker import processed_files, processing_lock, get_error_count
from .config import MAX_WORKERS


def create_api(processing_queue):
    """Create and configure the Flask API.
    
    Args:
        processing_queue: The processing queue to monitor and control
        
    Returns:
        Flask app instance
    """
    app = Flask(__name__)
    
    @app.route('/trigger-ingestion', methods=['POST'])
    def trigger_api():
        """Trigger reprocessing of documents."""
        print(f"Ingestion triggered via API at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Process documents in a separate thread to avoid blocking the response
        def trigger_processing():
            queue_unprocessed_files(processing_queue)
        
        threading.Thread(target=trigger_processing).start()
        
        return jsonify({
            "status": "success",
            "message": "Document ingestion triggered successfully",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint."""
        return jsonify({
            "status": "healthy",
            "service": "ingestion-service",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    @app.route('/status', methods=['GET'])
    def get_status():
        """Return the status of the ingestion service."""
        status = {
            "queue_size": processing_queue.qsize(),
            "processed_files": len(processed_files),
            "workers": MAX_WORKERS,
            "service": "ingestion-service",
            "timestamp": datetime.now().isoformat(),
            "errors": get_error_count()
        }
        
        return jsonify(status)
    
    @app.route('/force-process', methods=['POST'])
    def force_process():
        """Force processing of a specific file even if already processed."""
        data = request.json
        if not data or not data.get("file_path"):
            return jsonify({"status": "error", "message": "No file_path provided"}), 400
        
        file_path = data.get("file_path")
        
        # Remove from processed files if it's there
        with processing_lock:
            if file_path in processed_files:
                processed_files.remove(file_path)
        
        # Queue for processing
        processing_queue.put(file_path)
        
        return jsonify({
            "status": "success",
            "message": f"File {file_path} queued for forced processing",
            "timestamp": datetime.now().isoformat()
        })
    
    return app