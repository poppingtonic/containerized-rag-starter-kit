"""Document processing worker for the ingestion service."""

import os
import hashlib
from datetime import datetime
from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter

from .config import CHUNK_SIZE, CHUNK_OVERLAP
from .file_processors import process_file
from .file_tracker import is_file_processed, mark_file_processed, log_processing_error
from .database import check_document_exists, store_chunks_and_embeddings
from .embeddings import create_embeddings_batch


def process_document(file_path):
    """Process a single document and store it in the database.
    
    Args:
        file_path: Path to the document to process
    """
    # Skip already processed files
    if is_file_processed(file_path):
        print(f"Skipping already processed file: {os.path.basename(file_path)}")
        return
    
    try:
        # Skip files that don't exist anymore
        if not os.path.exists(file_path):
            print(f"File doesn't exist anymore, skipping: {file_path}")
            return
            
        # Extract metadata and content
        file_name = os.path.basename(file_path)
        file_extension = os.path.splitext(file_name)[1].lower()
        
        print(f"Starting processing of {file_name}...")
        
        # Process the file to extract content
        try:
            content, ocr_applied, file_type = process_file(file_path)
        except ValueError as e:
            print(f"Unsupported file type: {e}")
            return
            
        # Skip if we couldn't extract any content
        if not content or content.strip() == "":
            print(f"No content could be extracted from {file_name}")
            return
        
        # Clean content - remove any NUL characters that might cause database errors
        content = content.replace('\x00', '')
        
        # Create a file hash to uniquely identify the content
        content_hash = hashlib.md5(content.encode()).hexdigest()
        
        # Check if we already have a document with this content hash
        if check_document_exists(content_hash):
            print(f"Document {file_name} with same content hash already exists in database, skipping")
            mark_file_processed(file_path)
            return
        
        # Create metadata
        metadata = {
            "source": file_name,
            "extension": file_extension,
            "path": file_path,
            "mime_type": file_type,
            "ocr_applied": ocr_applied,
            "content_hash": content_hash,
            "processed_at": datetime.now().isoformat()
        }
        
        # Create document and chunk it
        document = Document(text=content)
        parser = SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        nodes = parser.get_nodes_from_documents([document])
        
        if not nodes:
            print(f"No chunks were created from {file_name}, skipping")
            return
            
        print(f"Created {len(nodes)} chunks for {file_name}, generating embeddings...")
        
        # Extract chunk texts
        chunk_texts = []
        for node in nodes:
            clean_text = node.text.replace('\x00', '')
            if clean_text.strip():  # Skip empty chunks
                chunk_texts.append(clean_text)
        
        if not chunk_texts:
            print(f"No valid chunks for {file_name}, skipping")
            return
        
        # Generate embeddings for all chunks
        embeddings = create_embeddings_batch(chunk_texts)
        
        # Store chunks and embeddings in database
        stored_count = store_chunks_and_embeddings(chunk_texts, embeddings, metadata)
        
        print(f"Successfully processed {file_name} - Created {stored_count} chunks with embeddings")
        
        # Mark the file as processed so we don't process it again
        mark_file_processed(file_path)
        
    except Exception as e:
        print(f"Error processing document {file_path}: {e}")
        log_processing_error(file_path, e)