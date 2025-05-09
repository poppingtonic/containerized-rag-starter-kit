#!/bin/bash

# Script to import documents from Zotero storage into GraphRAG system
# Usage: ./import_documents.sh [source_directory]

# Default source directory if not provided
SOURCE_DIR=${1:-"/home/mu/Zotero/storage"}
TARGET_DIR="$(pwd)/data"

# Ensure target directory exists
mkdir -p "$TARGET_DIR"

# Count documents before import
BEFORE_COUNT=$(find "$TARGET_DIR" -type f | wc -l)

# Find all PDFs recursively and copy them to the data directory
echo "Searching for PDF documents in $SOURCE_DIR..."
find "$SOURCE_DIR" -type f -name "*.pdf" -print0 | while IFS= read -r -d '' file; do
    # Extract filename
    filename=$(basename "$file")
    
    # Check if a file with the same name already exists
    if [ -f "$TARGET_DIR/$filename" ]; then
        echo "Skipping $filename (already exists)"
    else
        echo "Copying $filename"
        cp "$file" "$TARGET_DIR/"
    fi
done

# Find all DOCX files recursively and copy them to the data directory
echo "Searching for DOCX documents in $SOURCE_DIR..."
find "$SOURCE_DIR" -type f -name "*.docx" -print0 | while IFS= read -r -d '' file; do
    # Extract filename
    filename=$(basename "$file")
    
    # Check if a file with the same name already exists
    if [ -f "$TARGET_DIR/$filename" ]; then
        echo "Skipping $filename (already exists)"
    else
        echo "Copying $filename"
        cp "$file" "$TARGET_DIR/"
    fi
done

# Find all TXT files recursively and copy them to the data directory
echo "Searching for TXT documents in $SOURCE_DIR..."
find "$SOURCE_DIR" -type f -name "*.txt" -print0 | while IFS= read -r -d '' file; do
    # Extract filename
    filename=$(basename "$file")
    
    # Check if a file with the same name already exists
    if [ -f "$TARGET_DIR/$filename" ]; then
        echo "Skipping $filename (already exists)"
    else
        echo "Copying $filename"
        cp "$file" "$TARGET_DIR/"
    fi
done

# Count documents after import
AFTER_COUNT=$(find "$TARGET_DIR" -type f | wc -l)
NEW_COUNT=$((AFTER_COUNT - BEFORE_COUNT))

echo "Import complete: $NEW_COUNT new documents added to $TARGET_DIR"
echo "The ingestion service will automatically process these documents."