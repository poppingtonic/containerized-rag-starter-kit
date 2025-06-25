"""
Academic Paper Processing Module

Integrates GROBID and other academic parsing tools for processing research papers.
Provides structured parsing with section identification, citations, and references.
"""

import os
import glob
import sys
import warnings
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any
import hashlib
from datetime import datetime

try:
    import lxml
    import spacy
    from bs4 import BeautifulSoup
    from pydantic import BaseModel, Field
    from grobid_client.grobid_client import GrobidClient
    from collections.abc import Iterator
    from typing import Annotated, Literal
    
    # Try new import path first, then fallback
    try:
        from langchain_community.embeddings import OpenAIEmbeddings
    except ImportError:
        from langchain.embeddings.openai import OpenAIEmbeddings
    
    try:
        from haystack.components.converters import TextFileToDocument
        from haystack.components.preprocessors import DocumentCleaner, DocumentSplitter
        from haystack import Document
    except ImportError:
        # Haystack not available, will handle in functions
        TextFileToDocument = None
        DocumentCleaner = None
        DocumentSplitter = None
        Document = None
    
    ACADEMIC_DEPENDENCIES_AVAILABLE = True
    
except ImportError as e:
    print(f"Academic processing dependencies not available: {e}")
    ACADEMIC_DEPENDENCIES_AVAILABLE = False
    # Define minimal classes for basic functionality
    OpenAIEmbeddings = None
    TextFileToDocument = None
    DocumentCleaner = None
    DocumentSplitter = None
    Document = None

from config import OPENAI_API_KEY

# Initialize components
if ACADEMIC_DEPENDENCIES_AVAILABLE:
    try:
        nlp = spacy.load("en_core_web_md")
    except OSError:
        # Fallback to smaller model if available
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("Warning: No spaCy model found. Academic processing may be limited.")
            nlp = None
    
    if TextFileToDocument:
        txt_converter = TextFileToDocument()
    else:
        txt_converter = None
else:
    nlp = None
    txt_converter = None

# Configuration
GROBID_OUTPUT = Path("/app/data/grobid_output")
CACHE_DIR = Path("/app/data/parser_cache")

# Only create directories if we're running in the container environment
try:
    GROBID_OUTPUT.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
except PermissionError:
    # Running outside container, use local directories
    GROBID_OUTPUT = Path("./grobid_output")
    CACHE_DIR = Path("./parser_cache")
    GROBID_OUTPUT.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

SectionType = Literal["abstract", "main"]


def elem_to_text(elem, default=''):
    """Extract text from XML element."""
    if elem:
        return elem.getText()
    else:
        return default


def embed_paper_text(body: List[str]) -> Iterator[Tuple[str, List[float]]]:
    """Generate embeddings for paper text sections."""
    if not ACADEMIC_DEPENDENCIES_AVAILABLE:
        raise ValueError("Academic processing dependencies not available")
    
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not found in environment")
    
    api = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
    txt_embeddings = api.embed_documents(body)
    return zip(body, txt_embeddings)


def split_sentences(text: str) -> List[str]:
    """Split text into sentences using spaCy if available."""
    if nlp is None:
        # Simple fallback sentence splitting
        import re
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    doc = nlp(text)
    return [sent.text.strip() for sent in doc.sents if sent.text.strip()]


def parse_tei(tei: str) -> Tuple[Optional[str], List[str]]:
    """
    Parse TEI XML and extract abstract and body paragraphs with section titles.
    
    Args:
        tei: TEI XML string from GROBID
        
    Returns:
        Tuple of (abstract, paragraphs)
    """
    soup = BeautifulSoup(tei, 'lxml')
    
    # Extract abstract
    abstract = None
    if soup.abstract:
        abstract = soup.abstract.getText()
    
    # Extract paragraphs with section context
    paragraphs = []
    for p in soup.find_all('p'):
        section_title = ""
        sibling = p.previous_sibling
        if sibling and len(sibling.getText()) < 100:
            section_title = sibling.getText()
        
        paragraph_text = p.getText()
        if section_title:
            combined_text = f"{section_title}\n\n{paragraph_text}"
        else:
            combined_text = paragraph_text
            
        paragraphs.append(combined_text)

    return abstract, paragraphs


def save_pdf_text(paper_body: List[Dict], file_name: str):
    """Save parsed PDF text for debugging purposes."""
    paper_txt_dir = CACHE_DIR / "paper_txt"
    paper_txt_dir.mkdir(parents=True, exist_ok=True)
    
    with open(paper_txt_dir / f"{file_name}.txt", "w", encoding="utf-8") as f:
        for paragraph in paper_body:
            f.write(" ".join(paragraph["sentences"]) + "\n\n")


def process_with_grobid(file_path: Path) -> Tuple[Optional[str], List[str]]:
    """Process PDF with GROBID for structured academic parsing."""
    try:
        # Initialize GROBID client
        client = GrobidClient(config_path="./grobid_config.json")
        
        # Process with GROBID
        _, status, text = client.process_pdf(
            "processFulltextDocument", 
            str(file_path), 
            generateIDs=False, 
            consolidate_header=True,
            consolidate_citations=False,
            include_raw_citations=False,
            include_raw_affiliations=False,
            tei_coordinates=False,
            segment_sentences=True
        )
        
        if status == 200:
            abstract, paragraphs = parse_tei(text)
            return abstract, paragraphs
        else:
            print(f"GROBID processing failed with status {status}")
            return None, []
            
    except Exception as e:
        print(f"GROBID processing failed: {e}")
        return None, []


def process_with_fallback_api(file_path: Path) -> List[str]:
    """Fallback processing using external API or standard processors."""
    try:
        # Import here to avoid circular imports
        from .file_processors import process_file
        
        # Use the standard file processors as fallback
        content, _, _ = process_file(str(file_path))
        if content:
            # Split into paragraphs
            paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
            return paragraphs
        return []
    except Exception as e:
        print(f"Fallback processing failed: {e}")
        return []


def process_txt_with_preprocessing(file_path: Path) -> List[str]:
    """Process text files with Haystack 2.x preprocessing."""
    try:
        if not txt_converter or not DocumentCleaner or not DocumentSplitter:
            # Fallback if Haystack not available
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            # Simple paragraph splitting
            return [p.strip() for p in content.split('\n\n') if p.strip()]
        
        # Convert file to document
        result = txt_converter.run(sources=[str(file_path)])
        documents = result.get('documents', [])
        
        if not documents:
            return []
        
        # Clean documents
        cleaner = DocumentCleaner(
            remove_empty_lines=True,
            remove_extra_whitespaces=True,
            remove_repeated_substrings=False
        )
        cleaned_result = cleaner.run(documents=documents)
        cleaned_docs = cleaned_result.get('documents', documents)
        
        # Split documents
        splitter = DocumentSplitter(
            split_by="word",
            split_length=100,
            split_overlap=0,
            split_threshold=0
        )
        split_result = splitter.run(documents=cleaned_docs)
        split_docs = split_result.get('documents', [])
        
        return [doc.content for doc in split_docs if doc.content]
    except Exception as e:
        print(f"Text preprocessing failed: {e}")
        # Fallback to simple file reading
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return [p.strip() for p in content.split('\n\n') if p.strip()]
        except:
            return []


def parse_embed_file(file_path: Path) -> List[Dict[str, Any]]:
    """
    Main academic processing function that handles different file types.
    
    Args:
        file_path: Path to the academic paper
        
    Returns:
        List of processed paragraphs with embeddings and metadata
    """
    file_name = file_path.stem
    file_ext = file_path.suffix.lower()
    
    abstract = None
    paragraphs = []
    
    # Process based on file type
    if file_ext in [".pdf", ".PDF"]:
        # Try GROBID first for academic PDFs
        abstract, paragraphs = process_with_grobid(file_path)
        
        # If GROBID fails, try fallback
        if not paragraphs:
            paragraphs = process_with_fallback_api(file_path)
            
    elif file_ext in [".txt", ".TXT"]:
        paragraphs = process_txt_with_preprocessing(file_path)
        
    elif file_ext in ['.docx', '.doc']:
        paragraphs = process_with_fallback_api(file_path)
    
    else:
        raise ValueError(f"Unsupported file type: {file_ext}")
    
    # If no content extracted, return empty
    if not paragraphs and not abstract:
        return []
    
    # Prepare paper content for embedding
    if abstract and len(abstract.strip()) > 0:
        paper = [abstract] + paragraphs
    else:
        paper = paragraphs
    
    # Filter out empty content
    paper = [p for p in paper if p and p.strip()]
    
    if not paper:
        return []
    
    try:
        # Generate embeddings
        embed_text = embed_paper_text(paper)
    except Exception as e:
        warnings.warn(f"Failed to embed {file_path}: {e}")
        raise e

    # Build structured output
    body = []
    for paragraph, embed in embed_text:
        sentences = split_sentences(paragraph)
        body.append({
            "sentences": sentences,
            "embedding": embed,
            "sectionType": "abstract" if paragraph == abstract else "main",
        })
    
    # Save debug output
    save_pdf_text(body, file_name)
    
    return body


class SimpleParagraph(BaseModel):
    """Simplified paragraph model for academic papers."""
    sentences: List[str]
    embedding: List[float] = [0.0, 0.1]  # Default to minimize payload
    section_type: Annotated[SectionType, Field(alias="sectionType")]
    document_id: str = "unknown"

    def is_body_paragraph(self) -> bool:
        return self.section_type in ("abstract", "main")

    def is_empty(self) -> bool:
        return str(self).strip() == ""

    def __str__(self) -> str:
        return " ".join(self.sentences)

    def __hash__(self) -> int:
        return hash(str(self))


class SimplePaper(BaseModel):
    """Simplified paper model containing processed paragraphs."""
    paragraphs: List[SimpleParagraph]
    document_id: str = "unknown"
    
    @classmethod
    def load(cls, file_path: Path) -> "SimplePaper":
        """Load and process an academic paper from file."""
        document_id = file_path.name

        if file_path.suffix.lower() in [".pdf", ".txt", ".docx", ".doc"]:
            paragraph_dicts = parse_embed_file(file_path)
        else:
            raise ValueError(f"Unknown extension: {file_path.suffix}")
        
        return SimplePaper.ingest(paragraph_dicts, document_id)

    @classmethod
    def ingest(cls, paragraph_dicts: List[Dict], document_id: str = "unknown") -> "SimplePaper":
        """Create SimplePaper from processed paragraph data."""
        return SimplePaper.parse_obj(
            dict(paragraphs=paragraph_dicts, document_id=document_id)
        )

    def sentences(self) -> Iterator[str]:
        """Iterate over all sentences in the paper."""
        for paragraph in self.paragraphs:
            for sentence in paragraph.sentences:
                yield sentence
    
    def __str__(self) -> str:
        return "\n\n".join(str(p) for p in self.paragraphs)

    def nonempty_paragraphs(self) -> List[SimpleParagraph]:
        """Get all non-empty paragraphs."""
        return [p for p in self.paragraphs if not p.is_empty()]

    def dict(self, *args, **kwargs):
        """Override dict method to exclude paragraphs by default."""
        kwargs["exclude"] = {"paragraphs"}
        return super().dict(*args, **kwargs)


def process_academic_paper(file_path: str) -> Tuple[str, bool, str, List[Dict[str, Any]]]:
    """
    Process an academic paper and return content suitable for the ingestion pipeline.
    
    Args:
        file_path: Path to the academic paper
        
    Returns:
        Tuple of (content, ocr_applied, file_type, structured_data)
    """
    if not ACADEMIC_DEPENDENCIES_AVAILABLE:
        raise ValueError("Academic processing dependencies not available")
    
    path_obj = Path(file_path)
    
    try:
        # Process with academic pipeline
        paper = SimplePaper.load(path_obj)
        
        # Extract full text content
        content = str(paper)
        
        # Determine if OCR was applied (for scanned PDFs)
        ocr_applied = False  # GROBID handles this internally
        
        # Get file type
        file_type = f"application/academic-{path_obj.suffix[1:]}"
        
        # Prepare structured data for enhanced storage
        structured_data = []
        for para in paper.nonempty_paragraphs():
            structured_data.append({
                "text": str(para),
                "sentences": para.sentences,
                "section_type": para.section_type,
                "embedding": para.embedding
            })
        
        return content, ocr_applied, file_type, structured_data
        
    except Exception as e:
        print(f"Academic processing failed for {file_path}: {e}")
        raise e


def is_academic_paper(file_path: str) -> bool:
    """
    Determine if a file appears to be an academic paper based on path markers.
    
    Checks for 'ilri' or 'cgiar' in the file path to identify academic papers.
    """
    file_path_lower = file_path.lower()
    
    # Check for ILRI or CGIAR markers in the path
    if 'ilri' in file_path_lower or 'cgiar' in file_path_lower:
        return True
    
    # Check if it's in a specific academic directory
    if "academic" in file_path_lower or "papers" in file_path_lower:
        return True
    
    return False