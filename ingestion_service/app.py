#!/usr/bin/env python3
"""
Document Ingestion Service

A modular document processing service that:
- Watches for new documents in the data directory
- Processes PDFs, DOCX, TXT, and image files
- Extracts text using OCR when needed
- Generates embeddings and stores them in PostgreSQL
- Provides a REST API for monitoring and control

Optimized for handling large batches of files efficiently.
"""

import os
import time
import queue
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Import our modular components
from .config import DATA_DIR, MAX_WORKERS
from .file_tracker import load_processed_files, save_processed_files, processed_files
from .file_discovery import queue_unprocessed_files
from .document_processor import process_document
from .api import create_api


# Global processing queue
processing_queue = queue.Queue()


class DocumentHandler(FileSystemEventHandler):
    """File system event handler for watching new documents."""
    
    def on_created(self, event):
        if not event.is_directory:
            print(f"New file detected: {event.src_path}")
            processing_queue.put(event.src_path)


def queue_processor():
    """Worker thread that processes documents from the queue."""
    print("Starting queue processor thread")
    while True:
        try:
            # Get a file path from the queue
            file_path = processing_queue.get(timeout=1.0)
            
            # Process the file
            process_document(file_path)
            
            # Mark task as done
            processing_queue.task_done()
        except queue.Empty:
            # No documents in queue, sleep briefly
            time.sleep(0.1)
        except Exception as e:
            print(f"Error in queue processor: {e}")
            # Sleep a bit on errors to avoid hammering resources
            time.sleep(1.0)


def watch_documents():
    """Start the file system watcher for new documents."""
    print("Starting document watcher...")
    
    # Set up file watcher
    event_handler = DocumentHandler()
    observer = Observer()
    observer.schedule(event_handler, DATA_DIR, recursive=True)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


def check_for_trigger():
    """Check for trigger files to initiate document processing."""
    # Check primary trigger location
    trigger_file = '/app/trigger_ingestion'
    
    # Also check shared volume location (fallback mechanism)
    trigger_file_alt = '/app/graph_data/trigger_ingestion'
    
    for trigger_path in [trigger_file, trigger_file_alt]:
        if os.path.exists(trigger_path):
            print(f"Trigger file detected at {trigger_path} ({time.strftime('%Y-%m-%d %H:%M:%S')})")
            # Remove the trigger file
            try:
                os.remove(trigger_path)
                print("Trigger file removed")
            except Exception as e:
                print(f"Error removing trigger file: {e}")
            
            # Process all documents
            queue_unprocessed_files(processing_queue)
            break


def start_background_threads():
    """Start all background threads for the service."""
    threads = []
    
    # Start worker threads
    print(f"Starting {MAX_WORKERS} worker threads...")
    for i in range(MAX_WORKERS):
        processor = threading.Thread(target=queue_processor, daemon=True)
        processor.start()
        threads.append(processor)
    
    # Start the document watcher in a separate thread
    watcher_thread = threading.Thread(target=watch_documents, daemon=True)
    watcher_thread.start()
    threads.append(watcher_thread)
    
    # Start the trigger checker thread
    def trigger_checker():
        while True:
            try:
                check_for_trigger()
                time.sleep(10)  # Check every 10 seconds
            except Exception as e:
                print(f"Error in trigger checker: {e}")
                time.sleep(30)  # Back off on errors
    
    trigger_thread = threading.Thread(target=trigger_checker, daemon=True)
    trigger_thread.start()
    threads.append(trigger_thread)
    
    # Save state periodically
    def state_saver():
        while True:
            try:
                time.sleep(60)  # Save every minute
                save_processed_files()
            except Exception as e:
                print(f"Error saving state: {e}")
    
    state_thread = threading.Thread(target=state_saver, daemon=True)
    state_thread.start()
    threads.append(state_thread)
    
    # Print status periodically
    def status_printer():
        while True:
            try:
                time.sleep(30)  # Every 30 seconds
                print(f"Status: Queue size: {processing_queue.qsize()}, Processed files: {len(processed_files)}")
            except Exception as e:
                print(f"Error printing status: {e}")
    
    status_thread = threading.Thread(target=status_printer, daemon=True)
    status_thread.start()
    threads.append(status_thread)
    
    return threads


def main():
    """Main entry point for the ingestion service."""
    print("Starting document ingestion service...")
    print("=" * 50)
    
    # Load previously processed files
    load_processed_files()
    
    # Start all background threads
    threads = start_background_threads()
    
    # Process any existing documents on startup
    print("Processing existing documents...")
    queue_unprocessed_files(processing_queue)
    
    # Create and start the Flask API
    print("Starting API server...")
    app = create_api(processing_queue)
    
    try:
        # Start the Flask API (this blocks)
        app.run(host='0.0.0.0', port=5050)
    except KeyboardInterrupt:
        print("Shutting down ingestion service...")
        # Save final state
        save_processed_files()
        print("Service shut down complete.")


if __name__ == "__main__":
    # Wait for database to be ready
    time.sleep(5)
    main()