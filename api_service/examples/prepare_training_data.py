"""
Example: Prepare Training Data from Digest API

This script demonstrates how to prepare training data from existing
Digest API responses for GEPA optimization.
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from psycopg2 import sql


def fetch_digest_responses(db_url: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Fetch historical Digest API responses from database.

    Args:
        db_url: Database connection URL
        limit: Maximum number of responses to fetch

    Returns:
        List of response dictionaries
    """
    conn = psycopg2.connect(db_url)

    query = """
        SELECT
            question,
            answer,
            keywords,
            context,
            created_at
        FROM query_cache
        WHERE answer IS NOT NULL
        ORDER BY created_at DESC
        LIMIT %s
    """

    with conn.cursor() as cur:
        cur.execute(query, (limit,))
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()

    conn.close()

    responses = []
    for row in rows:
        response = dict(zip(columns, row))
        # Parse JSON fields if needed
        if isinstance(response.get('context'), str):
            try:
                response['context'] = json.loads(response['context'])
            except json.JSONDecodeError:
                pass
        if isinstance(response.get('keywords'), str):
            response['keywords'] = response['keywords'].split('|')

        responses.append(response)

    return responses


def create_synthetic_examples() -> List[Dict[str, Any]]:
    """
    Create synthetic training examples for initial bootstrapping.

    Returns:
        List of synthetic examples
    """
    examples = [
        {
            "question": "What genes are associated with Type 2 diabetes?",
            "answer": "Several genes are strongly associated with Type 2 diabetes (T2D), including TCF7L2, PPARG, FTO, KCNJ11, and NOTCH2. TCF7L2 is the most replicated T2D susceptibility gene across populations. PPARG and KCNJ11 encode targets of proven diabetes drugs (thiazolidinediones and sulfonylureas, respectively). FTO is associated with obesity-related diabetes risk.",
            "keywords": "Type&2&diabetes|T2D|TCF7L2|PPARG|FTO|KCNJ11|NOTCH2|diabetes&susceptibility|genetic&variants|diabetes&drugs",
            "context": [],
        },
        {
            "question": "How does insulin resistance develop?",
            "answer": "Insulin resistance develops through multiple mechanisms. Obesity, particularly visceral adiposity, leads to increased free fatty acids and inflammatory cytokines that impair insulin signaling. At the cellular level, excess nutrients activate stress kinases like JNK and IKK that phosphorylate and inhibit insulin receptor substrate proteins (IRS1/2). This reduces downstream signaling through PI3K/AKT pathways essential for glucose uptake.",
            "keywords": "insulin&resistance|obesity|visceral&adiposity|free&fatty&acids|inflammatory&cytokines|insulin&signaling|IRS1|IRS2|PI3K|AKT|glucose&uptake",
            "context": [],
        },
        {
            "question": "What are monogenic forms of diabetes?",
            "answer": "Monogenic diabetes results from single gene mutations and includes MODY (maturity-onset diabetes of the young) and neonatal diabetes. MODY accounts for 1-2% of diabetes cases and is caused by mutations in genes like HNF1A, HNF4A, HNF1B, and GCK. These genes regulate pancreatic beta-cell function and insulin secretion. Neonatal diabetes appears in the first 6 months of life and is often caused by mutations in KCNJ11 or ABCC8.",
            "keywords": "monogenic&diabetes|MODY|maturity-onset&diabetes|neonatal&diabetes|HNF1A|HNF4A|HNF1B|GCK|KCNJ11|ABCC8|beta-cell&function|insulin&secretion",
            "context": [],
        },
        {
            "question": "What is the role of GCK in glucose homeostasis?",
            "answer": "Glucokinase (GCK) acts as the glucose sensor in pancreatic beta-cells and hepatocytes. In beta-cells, GCK catalyzes the first step of glycolysis, converting glucose to glucose-6-phosphate. The rate of this reaction is proportional to glucose concentration, linking glucose sensing to insulin secretion. GCK mutations cause both hyperglycemia (loss-of-function) and hypoglycemia (gain-of-function), demonstrating its critical role in glucose homeostasis.",
            "keywords": "GCK|glucokinase|glucose&sensor|glucose&homeostasis|beta-cells|hepatocytes|glycolysis|glucose-6-phosphate|insulin&secretion|hyperglycemia|hypoglycemia",
            "context": [],
        },
        {
            "question": "How do GWAS studies identify diabetes genes?",
            "answer": "Genome-wide association studies (GWAS) identify diabetes susceptibility loci by testing hundreds of thousands to millions of genetic variants (SNPs) across the genome in large cohorts of cases and controls. Variants showing significant association (p < 5×10⁻⁸) mark genomic regions containing causal genes. However, most T2D variants have small effect sizes and are located in non-coding regions, requiring functional studies to identify causal genes and mechanisms.",
            "keywords": "GWAS|genome-wide&association&studies|diabetes&susceptibility|genetic&variants|SNPs|T2D|effect&sizes|non-coding&regions|functional&studies|causal&genes",
            "context": [],
        },
    ]

    return examples


def quality_filter_examples(
    examples: List[Dict[str, Any]],
    min_answer_length: int = 100,
    require_keywords: bool = True,
    check_keyword_format: bool = True
) -> List[Dict[str, Any]]:
    """
    Filter examples based on quality criteria.

    Args:
        examples: List of examples to filter
        min_answer_length: Minimum answer length
        require_keywords: Whether keywords are required
        check_keyword_format: Whether to check keyword formatting

    Returns:
        Filtered examples
    """
    filtered = []

    for ex in examples:
        # Check answer length
        if len(ex.get('answer', '')) < min_answer_length:
            continue

        # Check keywords exist
        if require_keywords and not ex.get('keywords'):
            continue

        # Check keyword format (no spaces, uses | and &)
        if check_keyword_format and ex.get('keywords'):
            keywords_str = ex['keywords']
            if isinstance(keywords_str, list):
                keywords_str = '|'.join(keywords_str)

            # Keywords should use | as separator and & for spaces
            if ' ' in keywords_str and '&' not in keywords_str:
                continue

        filtered.append(ex)

    return filtered


def prepare_training_data(
    db_url: Optional[str] = None,
    output_path: str = "./data/digest_training_data.json",
    use_synthetic: bool = True,
    fetch_from_db: bool = True,
    db_limit: int = 50
):
    """
    Prepare complete training dataset.

    Args:
        db_url: Database connection URL
        output_path: Output file path
        use_synthetic: Whether to include synthetic examples
        fetch_from_db: Whether to fetch from database
        db_limit: Maximum examples from database
    """
    all_examples = []

    # Add synthetic examples
    if use_synthetic:
        print("Creating synthetic examples...")
        synthetic = create_synthetic_examples()
        all_examples.extend(synthetic)
        print(f"Added {len(synthetic)} synthetic examples")

    # Fetch from database
    if fetch_from_db and db_url:
        print(f"Fetching up to {db_limit} examples from database...")
        try:
            db_examples = fetch_digest_responses(db_url, limit=db_limit)
            print(f"Fetched {len(db_examples)} examples from database")

            # Filter for quality
            print("Filtering examples for quality...")
            filtered = quality_filter_examples(db_examples)
            print(f"Retained {len(filtered)} high-quality examples")

            all_examples.extend(filtered)
        except Exception as e:
            print(f"Warning: Could not fetch from database: {e}")

    # Remove duplicates based on question
    seen_questions = set()
    unique_examples = []
    for ex in all_examples:
        q = ex['question'].lower().strip()
        if q not in seen_questions:
            seen_questions.add(q)
            unique_examples.append(ex)

    print(f"\nTotal unique examples: {len(unique_examples)}")

    # Save to file
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(unique_examples, f, indent=2, default=str)

    print(f"Training data saved to: {output_path}")

    # Print sample
    if unique_examples:
        print("\nSample example:")
        print(json.dumps(unique_examples[0], indent=2, default=str))


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Prepare training data for GEPA optimization"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./data/digest_training_data.json",
        help="Output file path"
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=os.getenv("DATABASE_URL"),
        help="Database connection URL"
    )
    parser.add_argument(
        "--no-synthetic",
        action="store_true",
        help="Exclude synthetic examples"
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Skip fetching from database"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum examples to fetch from database"
    )

    args = parser.parse_args()

    prepare_training_data(
        db_url=args.db_url,
        output_path=args.output,
        use_synthetic=not args.no_synthetic,
        fetch_from_db=not args.no_db,
        db_limit=args.limit,
    )


if __name__ == "__main__":
    main()
