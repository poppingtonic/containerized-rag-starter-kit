"""
Unstructured API Client

Client for interacting with unstructured-api service for document processing.
Supports a wide variety of document types including PDFs, Word docs, images,
presentations, spreadsheets, and more.
"""

import os
import requests
from typing import Dict, List, Optional, Any, BinaryIO, Union
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProcessedElement:
    """Represents a processed document element from unstructured-api"""
    type: str  # e.g., "Title", "NarrativeText", "Table", "ListItem"
    text: str
    metadata: Dict[str, Any]
    element_id: Optional[str] = None


@dataclass
class ProcessedDocument:
    """Represents a fully processed document"""
    elements: List[ProcessedElement]
    filename: str
    file_type: Optional[str] = None
    num_elements: int = 0
    metadata: Optional[Dict[str, Any]] = None


class UnstructuredClient:
    """
    Client for unstructured-api service.

    Supports processing of:
    - PDFs (including scanned PDFs with OCR)
    - Word documents (.doc, .docx)
    - PowerPoint presentations (.ppt, .pptx)
    - Excel spreadsheets (.xls, .xlsx)
    - Images (.jpg, .png, .tiff, etc.) with OCR
    - HTML and XML files
    - Emails (.eml, .msg)
    - Markdown files
    - CSV files
    - And many more...

    Example usage:
        client = UnstructuredClient(api_url="http://localhost:8001")
        result = client.process_file(
            filepath="/path/to/document.pdf",
            strategy="hi_res"  # Use high-resolution processing
        )
        for element in result.elements:
            print(f"{element.type}: {element.text}")
    """

    def __init__(self, api_url: str = "http://localhost:8001", api_key: Optional[str] = None):
        """
        Initialize unstructured API client.

        Args:
            api_url: Base URL of unstructured-api service
            api_key: Optional API key for authentication
        """
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()

        if api_key:
            self.session.headers.update({"unstructured-api-key": api_key})

    def process_file(
        self,
        filepath: Union[str, Path],
        strategy: str = "auto",
        ocr_languages: Optional[List[str]] = None,
        coordinates: bool = False,
        encoding: str = "utf-8",
        pdf_infer_table_structure: bool = True,
        skip_infer_table_types: Optional[List[str]] = None,
        extract_image_block_types: Optional[List[str]] = None,
        **kwargs
    ) -> ProcessedDocument:
        """
        Process a file using unstructured-api.

        Args:
            filepath: Path to the file to process
            strategy: Processing strategy ("auto", "fast", "hi_res", "ocr_only")
                - auto: Automatically choose best strategy
                - fast: Fast processing, may miss some content
                - hi_res: High-resolution processing with detailed extraction
                - ocr_only: Only use OCR for scanned documents
            ocr_languages: List of languages for OCR (e.g., ["eng", "spa"])
            coordinates: Include element coordinates in output
            encoding: Text encoding (default: utf-8)
            pdf_infer_table_structure: Infer table structure in PDFs
            skip_infer_table_types: Table types to skip inference
            extract_image_block_types: Types of image blocks to extract

        Returns:
            ProcessedDocument with extracted elements
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        with open(filepath, 'rb') as f:
            return self.process_file_content(
                file_content=f,
                filename=filepath.name,
                strategy=strategy,
                ocr_languages=ocr_languages,
                coordinates=coordinates,
                encoding=encoding,
                pdf_infer_table_structure=pdf_infer_table_structure,
                skip_infer_table_types=skip_infer_table_types,
                extract_image_block_types=extract_image_block_types,
                **kwargs
            )

    def process_file_content(
        self,
        file_content: BinaryIO,
        filename: str,
        strategy: str = "auto",
        ocr_languages: Optional[List[str]] = None,
        coordinates: bool = False,
        encoding: str = "utf-8",
        pdf_infer_table_structure: bool = True,
        skip_infer_table_types: Optional[List[str]] = None,
        extract_image_block_types: Optional[List[str]] = None,
        **kwargs
    ) -> ProcessedDocument:
        """
        Process file content from a file-like object.

        Args:
            file_content: File-like object containing document bytes
            filename: Original filename
            (other args same as process_file)

        Returns:
            ProcessedDocument with extracted elements
        """
        # Prepare request data
        files = {
            'files': (filename, file_content, self._get_content_type(filename))
        }

        data = {
            'strategy': strategy,
            'encoding': encoding,
        }

        if ocr_languages:
            data['ocr_languages'] = ocr_languages

        if coordinates:
            data['coordinates'] = 'true'

        if pdf_infer_table_structure:
            data['pdf_infer_table_structure'] = 'true'

        if skip_infer_table_types:
            data['skip_infer_table_types'] = skip_infer_table_types

        if extract_image_block_types:
            data['extract_image_block_types'] = extract_image_block_types

        # Add any additional kwargs
        data.update(kwargs)

        # Make API request
        url = f"{self.api_url}/general/v0/general"

        try:
            response = self.session.post(url, files=files, data=data)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Unstructured API request failed: {str(e)}")

        # Parse response
        elements_data = response.json()

        elements = []
        for elem_data in elements_data:
            element = ProcessedElement(
                type=elem_data.get('type', 'Unknown'),
                text=elem_data.get('text', ''),
                metadata=elem_data.get('metadata', {}),
                element_id=elem_data.get('element_id')
            )
            elements.append(element)

        return ProcessedDocument(
            elements=elements,
            filename=filename,
            file_type=self._get_file_type(filename),
            num_elements=len(elements),
            metadata={'strategy': strategy}
        )

    def process_directory(
        self,
        directory: Union[str, Path],
        recursive: bool = True,
        file_pattern: str = "*",
        **kwargs
    ) -> List[ProcessedDocument]:
        """
        Process all files in a directory.

        Args:
            directory: Path to directory
            recursive: Process subdirectories recursively
            file_pattern: Glob pattern for files to process (e.g., "*.pdf")
            **kwargs: Additional arguments passed to process_file()

        Returns:
            List of ProcessedDocument objects
        """
        directory = Path(directory)

        if not directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")

        results = []

        if recursive:
            files = directory.rglob(file_pattern)
        else:
            files = directory.glob(file_pattern)

        for filepath in files:
            if filepath.is_file():
                try:
                    result = self.process_file(filepath, **kwargs)
                    results.append(result)
                except Exception as e:
                    print(f"Error processing {filepath}: {str(e)}")

        return results

    def health_check(self) -> bool:
        """
        Check if unstructured-api service is healthy.

        Returns:
            True if service is responding
        """
        try:
            response = self.session.get(f"{self.api_url}/healthcheck", timeout=5)
            return response.status_code == 200
        except:
            return False

    def _get_content_type(self, filename: str) -> str:
        """Get content type from filename extension"""
        ext = Path(filename).suffix.lower()

        content_types = {
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.ppt': 'application/vnd.ms-powerpoint',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.txt': 'text/plain',
            '.html': 'text/html',
            '.xml': 'application/xml',
            '.csv': 'text/csv',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.tiff': 'image/tiff',
            '.eml': 'message/rfc822',
            '.msg': 'application/vnd.ms-outlook',
            '.md': 'text/markdown',
        }

        return content_types.get(ext, 'application/octet-stream')

    def _get_file_type(self, filename: str) -> str:
        """Get file type category from filename"""
        ext = Path(filename).suffix.lower()

        type_categories = {
            'document': ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt'],
            'presentation': ['.ppt', '.pptx', '.key', '.odp'],
            'spreadsheet': ['.xls', '.xlsx', '.csv', '.ods'],
            'image': ['.jpg', '.jpeg', '.png', '.gif', '.tiff', '.bmp', '.svg'],
            'email': ['.eml', '.msg'],
            'web': ['.html', '.htm', '.xml'],
            'code': ['.py', '.js', '.java', '.cpp', '.c', '.h', '.cs'],
            'data': ['.json', '.yaml', '.yml', '.xml'],
        }

        for category, extensions in type_categories.items():
            if ext in extensions:
                return category

        return 'unknown'

    def extract_text(self, processed_doc: ProcessedDocument) -> str:
        """
        Extract plain text from processed document.

        Args:
            processed_doc: ProcessedDocument object

        Returns:
            Combined text from all elements
        """
        return '\n\n'.join(elem.text for elem in processed_doc.elements if elem.text)

    def extract_tables(self, processed_doc: ProcessedDocument) -> List[ProcessedElement]:
        """
        Extract only table elements from processed document.

        Args:
            processed_doc: ProcessedDocument object

        Returns:
            List of table elements
        """
        return [elem for elem in processed_doc.elements if elem.type == 'Table']

    def extract_by_type(
        self,
        processed_doc: ProcessedDocument,
        element_type: str
    ) -> List[ProcessedElement]:
        """
        Extract elements of a specific type.

        Args:
            processed_doc: ProcessedDocument object
            element_type: Element type to extract (e.g., "Title", "NarrativeText")

        Returns:
            List of matching elements
        """
        return [elem for elem in processed_doc.elements if elem.type == element_type]
