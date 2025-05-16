#!/usr/bin/env python3
"""
Advanced document importer with OCR support for GraphRAG system.
This script imports documents from Zotero storage or other directory structures,
using OCR for scanned documents and images to make them searchable.
"""

import os
import sys
import shutil
import argparse
import hashlib
import json
import time
import requests
import logging
import mimetypes
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("import_with_ocr")

# OCR service configuration
OCR_SERVICE_URL = os.environ.get("OCR_SERVICE_URL", "http://localhost:1337")

# Initialize mime types
mimetypes.init()

def sanitize_filename(name):
    """Sanitize a filename to remove problematic characters."""
    # Replace spaces and problematic characters
    for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|', ' ']:
        name = name.replace(char, '_')
    return name

def get_document_hash(file_path):
    """Generate a hash of the document content for deduplication."""
    BUF_SIZE = 65536  # 64kb chunks
    sha1 = hashlib.sha1()
    
    with open(file_path, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha1.update(data)
    
    return sha1.hexdigest()

def needs_ocr(file_path):
    """Determine if a file needs OCR processing."""
    # Check file extension
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    
    # Images always need OCR
    if ext in ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif']:
        return True
        
    # For PDFs, we need to check if they're already searchable
    if ext == '.pdf':
        # Simplified check - in production we'd use a more robust method
        try:
            # Use OCR service endpoint to check
            check_url = f"{OCR_SERVICE_URL}/api/check"
            with open(file_path, 'rb') as f:
                files = {'file': f}
                response = requests.post(check_url, files=files)
                
            if response.status_code == 200:
                return response.json().get('ocr_needed', False)
            else:
                # Default to sending for OCR if we can't check
                return True
        except Exception as e:
            logger.warning(f"Error checking if PDF needs OCR: {e}")
            return True
    
    # Other document types don't need OCR
    return False

def process_with_ocr(file_path):
    """Process a file with OCR service and return the path to the OCR'd document."""
    try:
        logger.info(f"Sending {os.path.basename(file_path)} for OCR processing")
        
        # Upload file to OCR service
        process_url = f"{OCR_SERVICE_URL}/api/process"
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(process_url, files=files)
        
        if response.status_code != 202:
            logger.error(f"Error submitting file for OCR: {response.text}")
            return None
            
        # Get the status URL
        status_data = response.json()
        status_url = f"{OCR_SERVICE_URL}{status_data['status_url']}"
        
        # Poll for completion
        max_retries = 60  # 5 minutes with 5-second intervals
        for i in range(max_retries):
            time.sleep(5)
            status_response = requests.get(status_url)
            
            if status_response.status_code == 200:
                status = status_response.json()
                
                if status['status'] == 'completed':
                    # Download the processed file
                    file_name = os.path.basename(file_path)
                    download_url = f"{OCR_SERVICE_URL}/api/download/{file_name}"
                    download_response = requests.get(download_url)
                    
                    if download_response.status_code == 200:
                        output_path = f"{file_path}_ocr{os.path.splitext(file_path)[1]}"
                        with open(output_path, 'wb') as f:
                            f.write(download_response.content)
                        return output_path
                    else:
                        logger.error(f"Error downloading processed file: {download_response.text}")
                        return None
                        
                elif status['status'] == 'failed':
                    logger.error(f"OCR processing failed: {status.get('error', 'Unknown error')}")
                    return None
            
            # If we're still processing, continue polling
            logger.debug(f"OCR in progress, attempt {i+1}/{max_retries}")
            
        logger.error(f"OCR processing timed out after {max_retries} attempts")
        return None
        
    except Exception as e:
        logger.error(f"Error during OCR processing: {e}")
        return None

def process_and_copy_file(args, file_path, target_dir, document_metadata, file_hashes):
    """Process a single file with OCR if needed and copy to target directory."""
    try:
        # Get file info
        file_name = os.path.basename(file_path)
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        # Skip files with unsupported extensions
        supported_extensions = ['.pdf', '.docx', '.txt', '.jpg', '.jpeg', '.png', '.tiff', '.tif']
        if ext not in supported_extensions:
            return None
            
        # Get relative path from source
        rel_path = os.path.relpath(os.path.dirname(file_path), args.source_dir)
        
        # Generate hash for deduplication
        file_hash = get_document_hash(file_path)
        
        # Skip if we've already seen this exact file
        if file_hash in file_hashes:
            logger.info(f"Skipping {file_name} (duplicate of {file_hashes[file_hash]})")
            return None
            
        # Create destination filename with source directory info
        if rel_path != '.':
            # Include simplified path in filename for context
            path_component = sanitize_filename(rel_path)
            new_filename = f"{path_component}_{file_name}"
        else:
            new_filename = file_name
            
        # Ensure filename is unique
        base, ext = os.path.splitext(new_filename)
        counter = 1
        while os.path.exists(os.path.join(target_dir, new_filename)):
            new_filename = f"{base}_{counter}{ext}"
            counter += 1
            
        # Determine if OCR is needed and process
        ocr_applied = False
        final_source_path = file_path
        
        if args.ocr and (needs_ocr(file_path) or args.force_ocr):
            logger.info(f"OCR needed for {file_name}")
            
            # Only if OCR service is available and running
            try:
                health_check = requests.get(f"{OCR_SERVICE_URL}/api/health")
                if health_check.status_code == 200:
                    ocr_result = process_with_ocr(file_path)
                    if ocr_result:
                        final_source_path = ocr_result
                        ocr_applied = True
                        logger.info(f"OCR processing successful for {file_name}")
                else:
                    logger.warning(f"OCR service not available, skipping OCR for {file_name}")
            except Exception as e:
                logger.warning(f"Error checking OCR service: {e}, skipping OCR for {file_name}")
            
        # Determine target path
        if args.preserve_structure:
            target_subdir = os.path.join(target_dir, rel_path)
            os.makedirs(target_subdir, exist_ok=True)
            target_path = os.path.join(target_subdir, file_name)
        else:
            target_path = os.path.join(target_dir, new_filename)
            
        # Copy the file
        logger.info(f"Copying {file_name} to {os.path.relpath(target_path, os.getcwd())}")
        shutil.copy2(final_source_path, target_path)
        
        # Store metadata
        metadata = {
            'original_path': file_path,
            'source_dir': rel_path,
            'original_filename': file_name,
            'hash': file_hash,
            'ocr_applied': ocr_applied,
            'import_time': os.path.getmtime(file_path)
        }
        
        # Clean up OCR temp file if needed
        if ocr_applied and final_source_path != file_path:
            try:
                os.remove(final_source_path)
            except Exception as e:
                logger.warning(f"Error removing temporary OCR file: {e}")
                
        return os.path.basename(target_path), metadata
    
    except Exception as e:
        logger.error(f"Error processing file {file_path}: {e}")
        return None

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Import documents from Zotero storage with OCR support.')
    parser.add_argument('source_dir', nargs='?', default='/home/mu/Zotero/storage', 
                      help='Source directory containing documents (default: /home/mu/Zotero/storage)')
    parser.add_argument('--target-dir', default='./data',
                      help='Target directory for documents (default: ./data)')
    parser.add_argument('--preserve-structure', action='store_true',
                      help='Create subdirectories in target to preserve source structure')
    parser.add_argument('--metadata-file', default='./data/document_metadata.json',
                      help='JSON file to store document metadata (default: ./data/document_metadata.json)')
    parser.add_argument('--ocr', action='store_true', default=True,
                      help='Use OCR for scanned documents (default: True)')
    parser.add_argument('--no-ocr', dest='ocr', action='store_false',
                      help='Disable OCR processing')
    parser.add_argument('--force-ocr', action='store_true',
                      help='Force OCR processing for all documents')
    parser.add_argument('--ocr-service-url', default=OCR_SERVICE_URL,
                      help=f'URL for OCR service (default: {OCR_SERVICE_URL})')
    parser.add_argument('--threads', type=int, default=4,
                      help='Number of processing threads (default: 4)')
    
    args = parser.parse_args()
    
    global OCR_SERVICE_URL
    OCR_SERVICE_URL = args.ocr_service_url
    
    source_dir = os.path.abspath(args.source_dir)
    target_dir = os.path.abspath(args.target_dir)
    metadata_file = os.path.abspath(args.metadata_file)
    
    # Ensure target directory exists
    os.makedirs(target_dir, exist_ok=True)
    os.makedirs(os.path.dirname(metadata_file), exist_ok=True)
    
    # Load existing metadata if available
    document_metadata = {}
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r') as f:
                document_metadata = json.load(f)
        except json.JSONDecodeError:
            logger.warning(f"Could not parse existing metadata file. Starting fresh.")
    
    # Track file hashes to prevent duplicates
    file_hashes = {meta['hash']: filename for filename, meta in document_metadata.items()}
    
    # Count documents before import
    before_count = len(document_metadata)
    
    # File extensions to process
    extensions = ['.pdf', '.docx', '.txt', '.jpg', '.jpeg', '.png', '.tiff', '.tif']
    
    # Find all documents recursively
    logger.info(f"Searching for documents in {source_dir}...")
    
    # Collect all files
    all_files = []
    for root, _, files in os.walk(source_dir):
        for file in files:
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file_path)
            
            # Skip files with unsupported extensions
            if ext.lower() not in extensions:
                continue
                
            all_files.append(file_path)
    
    logger.info(f"Found {len(all_files)} candidate files")
    
    # Process files in parallel
    new_items = 0
    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        # Submit all tasks
        future_to_file = {
            executor.submit(
                process_and_copy_file, args, file_path, target_dir, document_metadata, file_hashes
            ): file_path for file_path in all_files
        }
        
        # Process results as they complete
        for future in as_completed(future_to_file):
            file_path = future_to_file[future]
            try:
                result = future.result()
                if result:
                    filename, metadata = result
                    document_metadata[filename] = metadata
                    file_hashes[metadata['hash']] = filename
                    new_items += 1
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
    
    # Save updated metadata
    with open(metadata_file, 'w') as f:
        json.dump(document_metadata, f, indent=2)
    
    # Report results
    after_count = len(document_metadata)
    
    logger.info(f"\nImport complete: {new_items} new documents added to {target_dir}")
    logger.info(f"Document metadata saved to {metadata_file}")
    logger.info("The ingestion service will automatically process these documents.")

if __name__ == "__main__":
    main()