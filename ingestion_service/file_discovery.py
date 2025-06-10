"""Fast file discovery for the ingestion service."""

import time
from pathlib import Path
from .config import DATA_DIR, GLOB_PATTERNS, FILE_BATCH_SIZE, QUEUE_BATCH_SIZE
from .file_tracker import get_unprocessed_files


def discover_files():
    """Discover all supported files in the data directory using fast glob patterns.
    
    Returns:
        List of file paths
    """
    print("Scanning for documents in data directory...")
    start_time = time.time()
    
    # Collect all file paths first using glob (much faster than os.walk)
    all_files = []
    data_path = Path(DATA_DIR)
    
    for ext in GLOB_PATTERNS:
        # Use recursive glob for all subdirectories
        pattern = f"**/{ext}"
        files = list(data_path.glob(pattern))
        all_files.extend([str(f) for f in files])
        
        # Also check uppercase extensions
        pattern_upper = f"**/{ext.upper()}"
        files_upper = list(data_path.glob(pattern_upper))
        all_files.extend([str(f) for f in files_upper])
    
    # Remove duplicates (in case of case-insensitive filesystems)
    all_files = list(set(all_files))
    document_count = len(all_files)
    
    discovery_time = time.time() - start_time
    print(f"Found {document_count} documents in {discovery_time:.2f} seconds")
    
    return all_files


def queue_unprocessed_files(processing_queue):
    """Discover files and queue unprocessed ones for processing.
    
    Args:
        processing_queue: Queue to add files to
        
    Returns:
        Number of files queued
    """
    # Discover all files
    all_files = discover_files()
    
    if not all_files:
        print("No documents found to process")
        return 0
    
    # Filter out already processed files
    start_filter_time = time.time()
    unprocessed_files = get_unprocessed_files(all_files)
    filter_time = time.time() - start_filter_time
    
    queued_count = len(unprocessed_files)
    print(f"Found {queued_count} unprocessed documents in {filter_time:.2f} seconds")
    
    if not unprocessed_files:
        print("All documents are already processed")
        return 0
    
    # Batch add to queue for better performance
    start_queue_time = time.time()
    for i in range(0, len(unprocessed_files), QUEUE_BATCH_SIZE):
        batch = unprocessed_files[i:i + QUEUE_BATCH_SIZE]
        
        # Add batch to queue
        for file_path in batch:
            processing_queue.put(file_path)
        
        # Print progress for large queues
        if queued_count > 1000 and i % (QUEUE_BATCH_SIZE * 10) == 0:
            print(f"Queued {min(i + QUEUE_BATCH_SIZE, queued_count)}/{queued_count} files...")
    
    queue_time = time.time() - start_queue_time
    total_time = time.time() - start_filter_time + queue_time
    
    print(f"Completed scan and queue in {total_time:.2f} seconds. Queue size: {processing_queue.qsize()}")
    return queued_count