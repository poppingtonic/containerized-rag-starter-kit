import os
import time
import json
import shutil
import logging
import tempfile
import subprocess
from pathlib import Path
from threading import Thread
from flask import Flask, request, jsonify
import ocrmypdf
import magic
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ocr_service")

# Initialize Flask app
app = Flask(__name__)

# Configuration
INPUT_DIR = os.environ.get("INPUT_DIR", "/app/input")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/app/output")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "5"))  # seconds

# Ensure directories exist
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Track processing status
processing_status = {}

def is_pdf_searchable(pdf_path):
    """Check if a PDF contains searchable text"""
    try:
        # Use pdfminer to check if the PDF contains text
        result = subprocess.run(
            ["pdftotext", "-f", "1", "-l", "1", pdf_path, "-"],
            capture_output=True,
            text=True,
            check=False
        )
        
        # If we get text, it's searchable
        return len(result.stdout.strip()) > 0
    except Exception as e:
        logger.error(f"Error checking if PDF is searchable: {e}")
        return False

def detect_file_type(file_path):
    """Detect file type and determine if OCR is needed"""
    mime = magic.Magic(mime=True)
    file_type = mime.from_file(file_path)
    
    ocr_needed = False
    supported = True
    
    if file_type.startswith('application/pdf'):
        # Check if PDF is already searchable or needs OCR
        ocr_needed = not is_pdf_searchable(file_path)
    elif file_type.startswith('image/'):
        # All images need OCR
        ocr_needed = True
    else:
        # Other types (text, docx, etc.) don't need OCR
        ocr_needed = False
        
    return {
        "file_type": file_type,
        "ocr_needed": ocr_needed,
        "supported": supported
    }

def process_pdf_with_ocr(input_path, output_path):
    """Process a PDF with OCR using ocrmypdf"""
    try:
        logger.info(f"Processing PDF with OCR: {input_path}")
        
        # Advanced OCR with automatic optimization
        ocrmypdf.ocr(
            input_path, 
            output_path,
            language="eng",
            deskew=True,              # Straighten skewed pages
            skip_text=True,           # Skip pages with text
            optimize=1,               # Optimize output size
            rotate_pages=True,        # Automatically rotate pages 
            remove_background=False,  # Keep background for visual quality
            progress_bar=False
        )
        
        logger.info(f"OCR completed for PDF: {input_path}")
        return True
    except Exception as e:
        logger.error(f"Error processing PDF with OCR: {e}")
        return False

def process_image_with_ocr(input_path, output_path):
    """Process an image file with OCR and convert to searchable PDF"""
    try:
        logger.info(f"Processing image with OCR: {input_path}")
        
        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Open the image
            image = Image.open(input_path)
            
            # Save as temporary PDF
            temp_pdf = os.path.join(temp_dir, "temp.pdf")
            image.save(temp_pdf, "PDF", resolution=300.0)
            
            # Process with OCR
            process_pdf_with_ocr(temp_pdf, output_path)
        
        logger.info(f"OCR completed for image: {input_path}")
        return True
    except Exception as e:
        logger.error(f"Error processing image with OCR: {e}")
        return False

def process_file(input_path, output_path):
    """Process a file and apply OCR if needed"""
    try:
        # Update status
        file_name = os.path.basename(input_path)
        processing_status[file_name] = {"status": "processing", "start_time": time.time()}
        
        # Detect file type and OCR needs
        file_info = detect_file_type(input_path)
        
        if not file_info["supported"]:
            logger.warning(f"Unsupported file type: {file_info['file_type']} for {input_path}")
            processing_status[file_name] = {
                "status": "failed", 
                "error": "Unsupported file type",
                "end_time": time.time()
            }
            return False
        
        if file_info["ocr_needed"]:
            logger.info(f"OCR needed for {input_path}")
            
            if file_info["file_type"].startswith('application/pdf'):
                success = process_pdf_with_ocr(input_path, output_path)
            elif file_info["file_type"].startswith('image/'):
                success = process_image_with_ocr(input_path, output_path)
            else:
                success = False
                logger.error(f"OCR requested but file type not supported: {file_info['file_type']}")
                
            if success:
                processing_status[file_name] = {
                    "status": "completed", 
                    "ocr_applied": True,
                    "end_time": time.time()
                }
                return True
            else:
                processing_status[file_name] = {
                    "status": "failed", 
                    "error": "OCR processing failed",
                    "end_time": time.time()
                }
                return False
        else:
            # File doesn't need OCR, just copy it
            logger.info(f"OCR not needed for {input_path}, copying file")
            shutil.copy2(input_path, output_path)
            processing_status[file_name] = {
                "status": "completed", 
                "ocr_applied": False,
                "end_time": time.time()
            }
            return True
            
    except Exception as e:
        logger.error(f"Error processing file {input_path}: {e}")
        processing_status[file_name] = {
            "status": "failed", 
            "error": str(e),
            "end_time": time.time()
        }
        return False

class FileEventHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
            
        input_path = event.src_path
        file_name = os.path.basename(input_path)
        output_path = os.path.join(OUTPUT_DIR, file_name)
        
        logger.info(f"New file detected: {input_path}")
        
        # Process in a separate thread to avoid blocking
        Thread(target=process_file, args=(input_path, output_path)).start()

# API endpoints
@app.route('/api/process', methods=['POST'])
def api_process():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
        
    # Save the uploaded file
    input_path = os.path.join(INPUT_DIR, file.filename)
    output_path = os.path.join(OUTPUT_DIR, file.filename)
    
    file.save(input_path)
    
    # Process the file
    Thread(target=process_file, args=(input_path, output_path)).start()
    
    return jsonify({
        "message": "File processing started",
        "file_name": file.filename,
        "status_url": f"/api/status/{file.filename}"
    }), 202

@app.route('/api/status/<filename>', methods=['GET'])
def api_status(filename):
    if filename in processing_status:
        return jsonify(processing_status[filename])
    else:
        return jsonify({"error": "File not found in processing history"}), 404

@app.route('/api/health', methods=['GET'])
def api_health():
    return jsonify({"status": "healthy"}), 200

def run_file_watcher():
    # Set up file watcher for the input directory
    event_handler = FileEventHandler()
    observer = Observer()
    observer.schedule(event_handler, INPUT_DIR, recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == '__main__':
    # Start file watcher in a background thread
    watcher_thread = Thread(target=run_file_watcher, daemon=True)
    watcher_thread.start()
    
    # Start the Flask app
    app.run(host='0.0.0.0', port=1337)
else:
    # When running with Gunicorn, start the file watcher
    watcher_thread = Thread(target=run_file_watcher, daemon=True)
    watcher_thread.start()