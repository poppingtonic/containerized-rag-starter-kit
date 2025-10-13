#!/usr/bin/env python3
"""
Test script to verify GEPA RAG system setup.

Usage:
    python test_gepa_setup.py
"""

import os
import sys
from pathlib import Path


def test_imports():
    """Test that all required packages can be imported."""
    print("Testing imports...")
    errors = []

    # Test DSPy
    try:
        import dspy
        print("  ✓ dspy")
    except ImportError as e:
        errors.append(f"  ✗ dspy: {e}")

    # Test psycopg2
    try:
        import psycopg2
        print("  ✓ psycopg2")
    except ImportError as e:
        errors.append(f"  ✗ psycopg2: {e}")

    # Test pgvector
    try:
        import pgvector
        print("  ✓ pgvector")
    except ImportError as e:
        errors.append(f"  ✗ pgvector: {e}")

    # Test OpenAI
    try:
        import openai
        print("  ✓ openai")
    except ImportError as e:
        errors.append(f"  ✗ openai: {e}")

    # Test pandas
    try:
        import pandas
        print("  ✓ pandas")
    except ImportError as e:
        errors.append(f"  ✗ pandas: {e}")

    if errors:
        print("\nErrors:")
        for error in errors:
            print(error)
        print("\nInstall missing packages with:")
        print("  pip install -r requirements-gepa.txt")
        return False

    print("\n✓ All imports successful!")
    return True


def test_environment():
    """Test environment variables."""
    print("\nTesting environment variables...")
    errors = []

    db_url = os.getenv("DATABASE_URL")
    if db_url:
        print("  ✓ DATABASE_URL is set")
    else:
        errors.append("  ✗ DATABASE_URL not set")

    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        print("  ✓ OPENAI_API_KEY is set")
    else:
        errors.append("  ✗ OPENAI_API_KEY not set")

    if errors:
        print("\nErrors:")
        for error in errors:
            print(error)
        print("\nSet environment variables:")
        print('  export DATABASE_URL="postgresql://user:pass@host:port/db"')
        print('  export OPENAI_API_KEY="sk-..."')
        return False

    print("\n✓ Environment configured!")
    return True


def test_module_imports():
    """Test that custom modules can be imported."""
    print("\nTesting custom modules...")
    errors = []

    # Add current directory to path
    sys.path.insert(0, str(Path(__file__).parent))

    try:
        from dspy_rag_system import (
            PgVectorRM,
            BasicRAG,
            MultiHopRAG,
            GEPAOptimizer,
            setup_consilience_rag,
        )
        print("  ✓ dspy_rag_system")
    except ImportError as e:
        errors.append(f"  ✗ dspy_rag_system: {e}")

    try:
        from gepa_training_pipeline import (
            TrainingConfig,
            GEPATrainer,
        )
        print("  ✓ gepa_training_pipeline")
    except ImportError as e:
        errors.append(f"  ✗ gepa_training_pipeline: {e}")

    if errors:
        print("\nErrors:")
        for error in errors:
            print(error)
        return False

    print("\n✓ All modules loaded!")
    return True


def test_directories():
    """Test that required directories exist."""
    print("\nChecking directories...")
    base_dir = Path(__file__).parent

    dirs = [
        base_dir / "data",
        base_dir / "examples",
        base_dir / "retrievers",
    ]

    all_exist = True
    for dir_path in dirs:
        if dir_path.exists():
            print(f"  ✓ {dir_path.relative_to(base_dir)}/")
        else:
            print(f"  ✗ {dir_path.relative_to(base_dir)}/ not found")
            all_exist = False

    if all_exist:
        print("\n✓ All directories exist!")
    else:
        print("\nCreate missing directories with:")
        print("  mkdir -p api_service/data api_service/examples")

    return all_exist


def test_database_connection():
    """Test database connection (optional)."""
    print("\nTesting database connection (optional)...")

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("  ⊗ Skipped (DATABASE_URL not set)")
        return True

    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        conn.close()
        print("  ✓ Database connection successful")
        return True
    except Exception as e:
        print(f"  ⚠ Database connection failed: {e}")
        print("    (This is optional - system will work without DB)")
        return True


def main():
    """Run all tests."""
    print("="*80)
    print("GEPA RAG System Setup Test")
    print("="*80)

    results = []

    # Run tests
    results.append(("Package imports", test_imports()))
    results.append(("Environment variables", test_environment()))
    results.append(("Custom modules", test_module_imports()))
    results.append(("Directories", test_directories()))
    results.append(("Database connection", test_database_connection()))

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False

    print("="*80)

    if all_passed:
        print("\n🎉 All tests passed! System is ready to use.")
        print("\nNext steps:")
        print("  1. Prepare training data:")
        print("     python examples/prepare_training_data.py")
        print("\n  2. Train the model:")
        print("     python gepa_training_pipeline.py --train")
        print("\n  3. See GEPA_RAG_README.md for full documentation")
        return 0
    else:
        print("\n⚠ Some tests failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
