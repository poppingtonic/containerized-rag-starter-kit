"""
Example: Train GEPA-optimized RAG System

This script demonstrates how to train and optimize a RAG system
using GEPA with few-shot examples from the Digest API data.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gepa_training_pipeline import (
    TrainingConfig,
    GEPATrainer,
    create_few_shot_examples,
)


def main():
    """Main training example."""

    # Configuration
    config = TrainingConfig(
        # Database and API
        db_url=os.getenv("DATABASE_URL"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),

        # Data
        data_path="./data/digest_training_data.json",
        output_dir="./gepa_outputs",

        # Model settings
        pg_table_name="document_chunks",
        use_multi_hop=True,

        # Training parameters
        num_trials=30,
        max_bootstrapped_demos=4,
        max_labeled_demos=8,
        num_candidates=10,

        # Data splits
        train_ratio=0.7,
        val_ratio=0.15,
        test_ratio=0.15,

        # Evaluation
        use_llm_metric=True,
        eval_threads=1,
    )

    # Save configuration
    config.to_json("./gepa_outputs/config.json")
    print("Configuration saved to ./gepa_outputs/config.json")

    # Initialize trainer
    print("\n" + "="*80)
    print("Initializing GEPA Trainer")
    print("="*80)
    trainer = GEPATrainer(config)

    # Load and prepare data
    trainer.load_data()

    # Evaluate baseline (unoptimized model)
    print("\n" + "="*80)
    print("Baseline Evaluation (Before Optimization)")
    print("="*80)
    baseline_score = trainer.evaluate(split='val')

    # Run GEPA optimization
    trainer.train()

    # Evaluate optimized model
    print("\n" + "="*80)
    print("Post-Optimization Evaluation")
    print("="*80)
    optimized_score = trainer.evaluate(split='val')

    # Calculate improvement
    improvement = (optimized_score - baseline_score) / baseline_score * 100
    print(f"\nImprovement: {improvement:+.2f}%")

    # Test on holdout set
    print("\n" + "="*80)
    print("Final Test Set Evaluation")
    print("="*80)
    test_score = trainer.evaluate(split='test')

    # Save optimized model
    trainer.save_model(model_name="gepa_rag_optimized")

    # Run some example queries
    print("\n" + "="*80)
    print("Example Queries")
    print("="*80)

    example_questions = [
        "What genes are related to diabetes?",
        "List genes related to increased hemolymph glucose",
        "What are the main findings about T2D susceptibility?",
    ]

    for question in example_questions:
        print("\n" + "-"*80)
        result = trainer.run_inference(question, verbose=True)
        print("-"*80)

    # Generate comprehensive benchmark
    print("\n" + "="*80)
    print("Final Benchmark Report")
    print("="*80)
    trainer.benchmark_comparison()

    print("\n" + "="*80)
    print("Training Complete!")
    print("="*80)
    print(f"Model saved to: ./gepa_outputs/gepa_rag_optimized.json")
    print(f"Configuration: ./gepa_outputs/gepa_rag_optimized_config.json")


if __name__ == "__main__":
    main()
