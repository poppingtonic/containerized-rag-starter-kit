#!/usr/bin/env python3
"""
Simple test script to verify academic processing integration.
"""

import sys
import os
sys.path.append('ingestion_service')

from ingestion_service.academic_processor import is_academic_paper

def test_academic_detection():
    """Test academic paper detection based on file paths."""
    
    # Test cases
    test_cases = [
        ("/data/ilri/research_paper.pdf", True),
        ("/documents/cgiar/animal_health.pdf", True),
        ("/home/user/ILRI_report.docx", True),
        ("/projects/CGIAR_data.txt", True),
        ("/random/document.pdf", False),
        ("/home/user/normal_file.txt", False),
        ("/academic/paper.pdf", True),
        ("/papers/research.pdf", True),
    ]
    
    print("Testing academic paper detection...")
    
    for file_path, expected in test_cases:
        result = is_academic_paper(file_path)
        status = "PASS" if result == expected else "FAIL"
        print(f"{status}: {file_path} -> {result} (expected {expected})")
    
    print("\nTest completed!")

if __name__ == "__main__":
    test_academic_detection()