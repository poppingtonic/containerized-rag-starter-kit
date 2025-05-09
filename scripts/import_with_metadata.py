#!/usr/bin/env python3
"""
Advanced document importer for GraphRAG system.
This script imports documents from Zotero storage or other directory structures,
preserving metadata about the source folders in the filename.
"""

import os
import sys
import shutil
import argparse
import hashlib
from pathlib import Path
import json

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

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Import documents from Zotero storage with metadata.')
    parser.add_argument('source_dir', nargs='?', default='/home/mu/Zotero/storage', 
                      help='Source directory containing documents (default: /home/mu/Zotero/storage)')
    parser.add_argument('--target-dir', default='./data',
                      help='Target directory for documents (default: ./data)')
    parser.add_argument('--preserve-structure', action='store_true',
                      help='Create subdirectories in target to preserve source structure')
    parser.add_argument('--metadata-file', default='./data/document_metadata.json',
                      help='JSON file to store document metadata (default: ./data/document_metadata.json)')
    
    args = parser.parse_args()
    
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
            print(f"Warning: Could not parse existing metadata file. Starting fresh.")
    
    # Track file hashes to prevent duplicates
    file_hashes = {meta['hash']: filename for filename, meta in document_metadata.items()}
    
    # Count documents before import
    before_count = len(document_metadata)
    
    # File extensions to process
    extensions = ['.pdf', '.docx', '.txt']
    
    # Find all documents recursively
    print(f"Searching for documents in {source_dir}...")
    
    for root, _, files in os.walk(source_dir):
        for file in files:
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file_path)
            
            # Skip files with unsupported extensions
            if ext.lower() not in extensions:
                continue
            
            # Get relative path from source
            rel_path = os.path.relpath(root, source_dir)
            
            # Generate hash for deduplication
            file_hash = get_document_hash(file_path)
            
            # Skip if we've already seen this exact file
            if file_hash in file_hashes:
                print(f"Skipping {file} (duplicate of {file_hashes[file_hash]})")
                continue
            
            # Create destination filename with source directory info
            if rel_path != '.':
                # Include simplified path in filename for context
                path_component = sanitize_filename(rel_path)
                new_filename = f"{path_component}_{file}"
            else:
                new_filename = file
            
            # Ensure filename is unique
            base, ext = os.path.splitext(new_filename)
            counter = 1
            while os.path.exists(os.path.join(target_dir, new_filename)):
                new_filename = f"{base}_{counter}{ext}"
                counter += 1
            
            # Determine target path
            if args.preserve_structure:
                target_subdir = os.path.join(target_dir, rel_path)
                os.makedirs(target_subdir, exist_ok=True)
                target_path = os.path.join(target_subdir, file)
            else:
                target_path = os.path.join(target_dir, new_filename)
            
            # Copy the file
            print(f"Copying {file} to {os.path.relpath(target_path, os.getcwd())}")
            shutil.copy2(file_path, target_path)
            
            # Store metadata
            document_metadata[os.path.basename(target_path)] = {
                'original_path': file_path,
                'source_dir': rel_path,
                'original_filename': file,
                'hash': file_hash,
                'import_time': os.path.getmtime(file_path)
            }
            
            # Update hash tracking
            file_hashes[file_hash] = os.path.basename(target_path)
    
    # Save updated metadata
    with open(metadata_file, 'w') as f:
        json.dump(document_metadata, f, indent=2)
    
    # Report results
    after_count = len(document_metadata)
    new_count = after_count - before_count
    
    print(f"\nImport complete: {new_count} new documents added to {target_dir}")
    print(f"Document metadata saved to {metadata_file}")
    print("The ingestion service will automatically process these documents.")

if __name__ == "__main__":
    main()