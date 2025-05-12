#!/usr/bin/env python3
import os
import time
import json
import threading
import argparse
import shutil
import hashlib
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import traceback
from datetime import datetime

# Configuration defaults
DEFAULT_WATCH_DIR = os.path.expanduser("~/Documents")  # Default directory to watch
DEFAULT_DATA_DIR = "./data"  # Default destination directory
DEFAULT_STATE_FILE = ".processed_files.json"  # Track processed files
DEFAULT_ERROR_LOG = ".error_log.json"  # Log processing errors
SUPPORTED_EXTENSIONS = ('.pdf', '.docx', '.txt', '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif')

# Global variables
processed_files = set()
processing_lock = threading.Lock()

# File tracking functions
def load_processed_files(state_file):
    """Load the set of already processed files"""
    global processed_files
    try:
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                processed_files = set(json.load(f))
                print(f"Loaded {len(processed_files)} previously processed files")
    except Exception as e:
        print(f"Error loading processed files: {e}")
        processed_files = set()

def save_processed_files(state_file):
    """Save the set of processed files"""
    try:
        with open(state_file, 'w') as f:
            json.dump(list(processed_files), f)
    except Exception as e:
        print(f"Error saving processed files: {e}")

def mark_file_processed(file_path, state_file):
    """Mark a file as successfully processed"""
    with processing_lock:
        processed_files.add(file_path)
        # Periodically save the state
        if len(processed_files) % 10 == 0:
            save_processed_files(state_file)

def is_file_processed(file_path):
    """Check if a file was already processed"""
    return file_path in processed_files

def log_processing_error(file_path, error, error_log):
    """Log an error that occurred during processing"""
    try:
        errors = {}
        if os.path.exists(error_log):
            with open(error_log, 'r') as f:
                errors = json.load(f)
        
        # Update or add the error
        errors[file_path] = {
            "error": str(error),
            "traceback": traceback.format_exc(),
            "timestamp": datetime.now().isoformat()
        }
        
        with open(error_log, 'w') as f:
            json.dump(errors, f, indent=2)
    except Exception as e:
        print(f"Error logging processing error: {e}")

def compute_file_hash(file_path):
    """Compute a hash of the file content"""
    try:
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception as e:
        print(f"Error computing file hash: {e}")
        return None

def copy_file_to_data_dir(source_path, data_dir):
    """Copy a file to the data directory, preserving its extension"""
    try:
        # Create data directory if it doesn't exist
        os.makedirs(data_dir, exist_ok=True)
        
        # Get source file name and extension
        file_name = os.path.basename(source_path)
        
        # Compute file hash to use as new filename (to avoid duplicates)
        file_hash = compute_file_hash(source_path)
        if not file_hash:
            file_hash = datetime.now().strftime("%Y%m%d%H%M%S")
        
        # Get the original extension
        _, ext = os.path.splitext(file_name)
        
        # Create new filename with hash
        new_filename = f"{file_hash}{ext}"
        
        # Full destination path
        dest_path = os.path.join(data_dir, new_filename)
        
        # If destination file already exists, don't overwrite
        if os.path.exists(dest_path):
            print(f"File with same hash already exists at {dest_path}, skipping copy")
            return dest_path
        
        # Copy the file
        shutil.copy2(source_path, dest_path)
        print(f"Copied {source_path} to {dest_path}")
        
        return dest_path
    except Exception as e:
        print(f"Error copying file {source_path}: {e}")
        traceback.print_exc()
        return None

# Function to process a document
def process_document(file_path, data_dir, state_file, error_log, trigger_api=False):
    """Process a document by copying it to the data directory"""
    try:
        # Skip if already processed
        if is_file_processed(file_path):
            print(f"Skipping already processed file: {file_path}")
            return
        
        # Skip non-existent files
        if not os.path.exists(file_path):
            print(f"File doesn't exist, skipping: {file_path}")
            return
        
        # Check if it's a supported file type
        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension not in SUPPORTED_EXTENSIONS:
            print(f"Unsupported file type: {file_extension}, skipping: {file_path}")
            return
        
        # Copy the file to data directory
        dest_path = copy_file_to_data_dir(file_path, data_dir)
        if not dest_path:
            print(f"Failed to copy {file_path} to data directory")
            return
        
        # Mark the original file as processed
        mark_file_processed(file_path, state_file)
        
        # Trigger the ingestion API if requested
        if trigger_api:
            try:
                import requests
                response = requests.post("http://localhost:5050/trigger-ingestion")
                print(f"Triggered ingestion API: {response.status_code} - {response.text}")
            except Exception as e:
                print(f"Error triggering ingestion API: {e}")
        
        print(f"Successfully processed {file_path}")
        
    except Exception as e:
        print(f"Error processing document {file_path}: {e}")
        traceback.print_exc()
        log_processing_error(file_path, e, error_log)

# File watcher class
class DocumentHandler(FileSystemEventHandler):
    def __init__(self, data_dir, state_file, error_log, trigger_api=False):
        self.data_dir = data_dir
        self.state_file = state_file
        self.error_log = error_log
        self.trigger_api = trigger_api
    
    def on_created(self, event):
        if not event.is_directory:
            print(f"New file detected: {event.src_path}")
            process_document(event.src_path, self.data_dir, self.state_file, self.error_log, self.trigger_api)

# Process all existing documents in the watch directory
def process_all_documents(watch_dir, data_dir, state_file, error_log, trigger_api=False):
    """Process all documents in the watch directory"""
    print(f"Scanning for documents in {watch_dir}...")
    document_count = 0
    processed_count = 0
    
    for root, _, files in os.walk(watch_dir):
        for file in files:
            file_extension = os.path.splitext(file)[1].lower()
            if file_extension in SUPPORTED_EXTENSIONS:
                document_count += 1
                file_path = os.path.join(root, file)
                
                # Skip already processed files
                if is_file_processed(file_path):
                    continue
                
                # Process the file
                process_document(file_path, data_dir, state_file, error_log, trigger_api)
                processed_count += 1
    
    print(f"Found {document_count} documents, processed {processed_count}")
    return processed_count

# Main function
def main():
    parser = argparse.ArgumentParser(description='Watch a directory for files and copy them to a data directory.')
    parser.add_argument('-w', '--watch-dir', default=DEFAULT_WATCH_DIR, 
                        help=f'Directory to watch for new files (default: {DEFAULT_WATCH_DIR})')
    parser.add_argument('-d', '--data-dir', default=DEFAULT_DATA_DIR, 
                        help=f'Directory to copy files to (default: {DEFAULT_DATA_DIR})')
    parser.add_argument('-s', '--state-file', default=DEFAULT_STATE_FILE, 
                        help=f'File to store processing state (default: {DEFAULT_STATE_FILE})')
    parser.add_argument('-e', '--error-log', default=DEFAULT_ERROR_LOG, 
                        help=f'File to log processing errors (default: {DEFAULT_ERROR_LOG})')
    parser.add_argument('-r', '--recursive', action='store_true', 
                        help='Watch directory recursively')
    parser.add_argument('-t', '--trigger-api', action='store_true', 
                        help='Trigger the ingestion API after copying files')
    parser.add_argument('-p', '--process-existing', action='store_true', 
                        help='Process existing files in the watch directory on startup')
    
    args = parser.parse_args()
    
    # Ensure paths are absolute
    watch_dir = os.path.abspath(os.path.expanduser(args.watch_dir))
    data_dir = os.path.abspath(os.path.expanduser(args.data_dir))
    
    print(f"Starting file watcher...")
    print(f"Watch directory: {watch_dir}")
    print(f"Data directory: {data_dir}")
    print(f"Recursive mode: {'enabled' if args.recursive else 'disabled'}")
    print(f"Trigger API: {'enabled' if args.trigger_api else 'disabled'}")
    
    # Create directories if they don't exist
    os.makedirs(watch_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)
    
    # Load previously processed files
    load_processed_files(args.state_file)
    
    # Process existing files if requested
    if args.process_existing:
        process_all_documents(watch_dir, data_dir, args.state_file, args.error_log, args.trigger_api)
    
    # Set up the file watcher
    event_handler = DocumentHandler(data_dir, args.state_file, args.error_log, args.trigger_api)
    observer = Observer()
    observer.schedule(event_handler, watch_dir, recursive=args.recursive)
    observer.start()
    
    # Save state periodically
    def state_saver():
        while True:
            try:
                time.sleep(60)  # Save every minute
                save_processed_files(args.state_file)
            except Exception as e:
                print(f"Error saving state: {e}")
    
    state_thread = threading.Thread(target=state_saver, daemon=True)
    state_thread.start()
    
    # Print status periodically
    def status_printer():
        while True:
            try:
                time.sleep(30)  # Every 30 seconds
                print(f"Status: Processed files: {len(processed_files)}")
            except Exception as e:
                print(f"Error printing status: {e}")
    
    status_thread = threading.Thread(target=status_printer, daemon=True)
    status_thread.start()
    
    # Keep the main thread running
    try:
        print("Watcher started. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping file watcher...")
        observer.stop()
    
    # Wait for the observer to complete
    observer.join()
    
    # Save final state
    save_processed_files(args.state_file)
    print("File watcher stopped.")

if __name__ == "__main__":
    main()