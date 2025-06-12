"""File tracking and state management for the ingestion service."""

import os
import json
import time
import threading
import traceback
from datetime import datetime
from config import STATE_FILE, ERROR_LOG

# Global variables
processed_files = set()
processing_lock = threading.Lock()


def load_processed_files():
    """Load the set of already processed files."""
    global processed_files
    try:
        if os.path.exists(STATE_FILE):
            print("Loading previously processed files...")
            start_time = time.time()
            with open(STATE_FILE, 'r') as f:
                file_list = json.load(f)
                processed_files = set(file_list)
                load_time = time.time() - start_time
                print(f"Loaded {len(processed_files)} previously processed files in {load_time:.2f} seconds")
    except Exception as e:
        print(f"Error loading processed files: {e}")
        processed_files = set()


def save_processed_files():
    """Save the set of processed files."""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(list(processed_files), f)
    except Exception as e:
        print(f"Error saving processed files: {e}")


def mark_file_processed(file_path):
    """Mark a file as successfully processed."""
    with processing_lock:
        processed_files.add(file_path)
        # Periodically save the state
        if len(processed_files) % 10 == 0:
            save_processed_files()


def is_file_processed(file_path):
    """Check if a file was already processed."""
    return file_path in processed_files


def get_unprocessed_files(all_files):
    """Filter a list of files to return only unprocessed ones.
    
    Args:
        all_files: List of file paths
        
    Returns:
        List of unprocessed file paths
    """
    unprocessed_files = []
    batch_size = 1000  # Process in batches to avoid memory issues
    
    for i in range(0, len(all_files), batch_size):
        batch = all_files[i:i + batch_size]
        
        # Filter out processed files from this batch
        with processing_lock:
            unprocessed_batch = [f for f in batch if f not in processed_files]
        
        unprocessed_files.extend(unprocessed_batch)
        
        # Print progress for large batches
        if len(all_files) > 5000 and i % (batch_size * 10) == 0:
            print(f"Filtered {i + len(batch)}/{len(all_files)} files...")
    
    return unprocessed_files


def log_processing_error(file_path, error):
    """Log an error that occurred during processing."""
    try:
        errors = {}
        if os.path.exists(ERROR_LOG):
            with open(ERROR_LOG, 'r') as f:
                errors = json.load(f)
        
        # Update or add the error
        errors[file_path] = {
            "error": str(error),
            "traceback": traceback.format_exc(),
            "timestamp": datetime.now().isoformat()
        }
        
        with open(ERROR_LOG, 'w') as f:
            json.dump(errors, f, indent=2)
    except Exception as e:
        print(f"Error logging processing error: {e}")


def get_error_count():
    """Get the number of processing errors."""
    try:
        if os.path.exists(ERROR_LOG):
            with open(ERROR_LOG, 'r') as f:
                error_data = json.load(f)
                return len(error_data)
        return 0
    except:
        return "unknown"