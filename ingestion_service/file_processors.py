"""File processing modules for different document types."""

import os
import pypdf
import docx
import magic
from PIL import Image
import pytesseract
from pdf2image import convert_from_path


def clean_text(text):
    """Clean text by removing null characters and non-printable characters."""
    if not text:
        return ""
    
    # Clean any binary or NULL characters
    text = text.replace('\x00', '')
    # Replace any other non-printable characters
    text = ''.join(c if c.isprintable() or c.isspace() else ' ' for c in text)
    return text


def is_pdf_searchable(file_path):
    """Check if a PDF contains searchable text."""
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = pypdf.PdfReader(file)
            # Check first few pages for text
            for i in range(min(3, len(pdf_reader.pages))):
                if pdf_reader.pages[i].extract_text().strip():
                    return True
        return False
    except Exception as e:
        print(f"Error checking if PDF is searchable: {e}")
        return False


def process_pdf_with_ocr(file_path):
    """Process a PDF that needs OCR."""
    print(f"Performing OCR on {os.path.basename(file_path)}")
    text = ""
    try:
        # Convert PDF to images
        images = convert_from_path(file_path)
        
        # Perform OCR on each page
        for i, image in enumerate(images):
            try:
                page_text = pytesseract.image_to_string(image, lang='eng')
                page_text = clean_text(page_text)
                text += f"\n\nPage {i+1}:\n{page_text}"
            except Exception as e:
                print(f"Error OCR-ing page {i+1}: {e}")
                text += f"\n\nPage {i+1}: [OCR ERROR: {str(e)}]"
            
        return text
    except Exception as e:
        print(f"Error performing OCR on PDF: {e}")
        # Fallback to regular processing
        return process_pdf_without_ocr(file_path)


def process_pdf_without_ocr(file_path):
    """Process a PDF without OCR."""
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = pypdf.PdfReader(file)
            text = ""
            for i, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text += clean_text(page_text)
                except Exception as e:
                    print(f"Error extracting text from page {i+1}: {e}")
            return text
    except Exception as e:
        print(f"Error processing PDF without OCR: {e}")
        return ""


def process_pdf(file_path):
    """Process a PDF file, using OCR if needed."""
    if not is_pdf_searchable(file_path):
        return process_pdf_with_ocr(file_path)
    else:
        return process_pdf_without_ocr(file_path)


def process_image(file_path):
    """Process an image file with OCR."""
    try:
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image, lang='eng')
        return clean_text(text)
    except Exception as e:
        print(f"Error processing image with OCR: {e}")
        return ""


def process_docx(file_path):
    """Process a DOCX file."""
    try:
        doc = docx.Document(file_path)
        text = " ".join([para.text for para in doc.paragraphs])
        return clean_text(text)
    except Exception as e:
        print(f"Error processing DOCX file: {e}")
        return ""


def process_txt(file_path):
    """Process a text file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            text = file.read()
    except UnicodeDecodeError:
        # Try with a different encoding
        try:
            with open(file_path, 'r', encoding='latin-1') as file:
                text = file.read()
        except Exception as e:
            print(f"Error processing text file with latin-1 encoding: {e}")
            return ""
    except Exception as e:
        print(f"Error processing text file: {e}")
        return ""
    
    return clean_text(text)


def process_file(file_path):
    """Process a file based on its type and return the extracted text.
    
    Args:
        file_path: Path to the file to process
        
    Returns:
        tuple: (content, ocr_applied, file_type)
    """
    # Get file info
    file_extension = os.path.splitext(file_path)[1].lower()
    
    # Get mime type for more accurate file type detection
    mime = magic.Magic(mime=True)
    file_type = mime.from_file(file_path)
    
    ocr_applied = False
    content = ""
    
    # Process based on file type
    if file_extension == '.pdf':
        # Check if PDF needs OCR
        if not is_pdf_searchable(file_path):
            content = process_pdf_with_ocr(file_path)
            ocr_applied = True
        else:
            content = process_pdf_without_ocr(file_path)
    elif file_extension == '.docx':
        content = process_docx(file_path)
    elif file_extension == '.txt':
        content = process_txt(file_path)
    elif file_extension in ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif']:
        content = process_image(file_path)
        ocr_applied = True
    else:
        # Try to determine type by MIME
        if file_type.startswith('application/pdf'):
            if not is_pdf_searchable(file_path):
                content = process_pdf_with_ocr(file_path)
                ocr_applied = True
            else:
                content = process_pdf_without_ocr(file_path)
        elif file_type.startswith('image/'):
            content = process_image(file_path)
            ocr_applied = True
        else:
            raise ValueError(f"Unsupported file type: {file_extension} (MIME: {file_type})")
    
    return content, ocr_applied, file_type