#!/usr/bin/env python3
"""
Test script to verify Haystack 2.x migration in academic processor.
"""

import tempfile
from pathlib import Path

def test_haystack_imports():
    """Test that Haystack 2.x imports work correctly."""
    print("Testing Haystack 2.x imports...")
    try:
        from haystack.components.converters import TextFileToDocument
        from haystack.components.preprocessors import DocumentCleaner, DocumentSplitter
        from haystack import Document
        print("✓ Haystack 2.x imports successful")
        return True
    except ImportError as e:
        print(f"✗ Haystack 2.x import failed: {e}")
        return False

def test_text_processing():
    """Test text file processing with new Haystack API."""
    print("\nTesting text file processing...")
    
    # Create a temporary test file
    test_content = """This is a test document for Haystack migration.

This is the second paragraph with some content.

And here is the third paragraph to test splitting."""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(test_content)
        test_file = Path(f.name)
    
    try:
        # Import the academic processor function
        import sys
        sys.path.append('/home/mu/src/writehere-graphrag/ingestion_service')
        from academic_processor import process_txt_with_preprocessing
        
        # Process the test file
        result = process_txt_with_preprocessing(test_file)
        
        if result:
            print(f"✓ Text processing successful, got {len(result)} chunks")
            for i, chunk in enumerate(result[:3]):  # Show first 3 chunks
                print(f"  Chunk {i+1}: {chunk[:50]}...")
            return True
        else:
            print("✗ Text processing returned empty result")
            return False
            
    except Exception as e:
        print(f"✗ Text processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        test_file.unlink(missing_ok=True)

def test_academic_processor_availability():
    """Test that academic processor can be imported."""
    print("\nTesting academic processor import...")
    try:
        import sys
        sys.path.append('/home/mu/src/writehere-graphrag/ingestion_service')
        from academic_processor import ACADEMIC_DEPENDENCIES_AVAILABLE
        
        if ACADEMIC_DEPENDENCIES_AVAILABLE:
            print("✓ Academic dependencies available")
        else:
            print("⚠ Academic dependencies not fully available")
        
        # Try importing the main processing function
        from academic_processor import process_academic_paper, is_academic_paper
        print("✓ Main functions imported successfully")
        return True
        
    except Exception as e:
        print(f"✗ Academic processor import failed: {e}")
        return False

if __name__ == "__main__":
    print("Haystack 2.x Migration Test")
    print("=" * 40)
    
    tests_passed = 0
    total_tests = 3
    
    if test_haystack_imports():
        tests_passed += 1
    
    if test_academic_processor_availability():
        tests_passed += 1
        
    if test_text_processing():
        tests_passed += 1
    
    print(f"\n{tests_passed}/{total_tests} tests passed")
    
    if tests_passed < total_tests:
        print("\nNote: Some tests failed. This might be expected if running outside the Docker container.")
        print("The academic processor has fallback mechanisms for when Haystack is not available.")