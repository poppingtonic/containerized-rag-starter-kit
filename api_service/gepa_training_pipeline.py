"""
GEPA Training Pipeline for Consilience RAG System

This script provides a complete training pipeline for optimizing the RAG system
using GEPA (Genetic-Pareto) with few-shot examples.

Usage:
    python gepa_training_pipeline.py --config config.json
    python gepa_training_pipeline.py --train --evaluate --save-model
"""

import os
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

import dspy
from dspy.datasets import DataLoader

from dspy_rag_system import (
    setup_consilience_rag,
    optimize_consilience_rag,
    GEPAOptimizer,
    BasicRAG,
    MultiHopRAG,
    create_llm_metric,
    create_simple_metric,
)


# ============================================================================
# Data Loading and Preparation
# ============================================================================

def load_training_data(
    data_path: str,
    input_keys: tuple = ("question",),
    fields: Optional[List[str]] = None
) -> List[dspy.Example]:
    """
    Load training data from JSON file.

    Args:
        data_path: Path to JSON data file
        input_keys: Tuple of input field names
        fields: List of fields to extract

    Returns:
        List of dspy.Example objects
    """
    if fields is None:
        fields = ["question", "answer", "context", "keywords"]

    loader = DataLoader()

    if data_path.endswith('.json'):
        dataset = loader.from_json(
            data_path,
            fields=fields,
            input_keys=input_keys
        )
    else:
        raise ValueError(f"Unsupported file format: {data_path}")

    return dataset


def prepare_dataset_splits(
    dataset: List[dspy.Example],
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    input_keys: tuple = ("question",)
) -> Dict[str, List[dspy.Example]]:
    """
    Split dataset into train, validation, and test sets.

    Args:
        dataset: Full dataset
        train_ratio: Proportion for training
        val_ratio: Proportion for validation
        test_ratio: Proportion for testing
        input_keys: Input field names

    Returns:
        Dictionary with 'train', 'val', 'test' splits
    """
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6, \
        "Ratios must sum to 1.0"

    total = len(dataset)
    train_size = int(total * train_ratio)
    val_size = int(total * val_ratio)

    # Split dataset
    trainset = dataset[:train_size]
    valset = dataset[train_size:train_size + val_size]
    testset = dataset[train_size + val_size:]

    # Convert to input format
    trainset = [ex.with_inputs(*input_keys) for ex in trainset]
    valset = [ex.with_inputs(*input_keys) for ex in valset]
    testset = [ex.with_inputs(*input_keys) for ex in testset]

    return {
        'train': trainset,
        'val': valset,
        'test': testset
    }


def create_few_shot_examples(
    dataset: List[dspy.Example],
    num_examples: int = 5,
    quality_filter: bool = True
) -> List[dspy.Example]:
    """
    Create high-quality few-shot examples from dataset.

    Args:
        dataset: Full dataset
        num_examples: Number of few-shot examples
        quality_filter: Whether to filter for quality

    Returns:
        List of few-shot examples
    """
    if quality_filter:
        # Filter examples with properly formatted keywords (no spaces)
        quality_examples = [
            ex for ex in dataset
            if hasattr(ex, 'keywords') and
            ' ' not in '|'.join(ex.keywords if isinstance(ex.keywords, list) else [ex.keywords])
        ]
        examples = quality_examples[:num_examples]
    else:
        examples = dataset[:num_examples]

    return examples


# ============================================================================
# Training and Optimization
# ============================================================================

class TrainingConfig:
    """Configuration for GEPA training."""

    def __init__(
        self,
        db_url: str,
        openai_api_key: str,
        data_path: str,
        output_dir: str = "./gepa_outputs",
        pg_table_name: str = "document_chunks",
        use_multi_hop: bool = True,
        use_gepa: bool = True,
        gepa_auto: str = "light",
        gepa_num_threads: int = 1,
        gepa_track_stats: bool = True,
        gepa_use_merge: bool = False,
        num_trials: int = 30,
        max_bootstrapped_demos: int = 4,
        max_labeled_demos: int = 8,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        use_llm_metric: bool = True,
        eval_threads: int = 1,
    ):
        """Initialize training configuration."""
        self.db_url = db_url
        self.openai_api_key = openai_api_key
        self.data_path = data_path
        self.output_dir = output_dir
        self.pg_table_name = pg_table_name
        self.use_multi_hop = use_multi_hop
        self.use_gepa = use_gepa
        self.gepa_auto = gepa_auto
        self.gepa_num_threads = gepa_num_threads
        self.gepa_track_stats = gepa_track_stats
        self.gepa_use_merge = gepa_use_merge
        self.num_trials = num_trials
        self.max_bootstrapped_demos = max_bootstrapped_demos
        self.max_labeled_demos = max_labeled_demos
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.use_llm_metric = use_llm_metric
        self.eval_threads = eval_threads

    @classmethod
    def from_json(cls, config_path: str) -> "TrainingConfig":
        """Load configuration from JSON file."""
        with open(config_path, 'r') as f:
            config_dict = json.load(f)
        return cls(**config_dict)

    def to_json(self, config_path: str):
        """Save configuration to JSON file."""
        with open(config_path, 'w') as f:
            json.dump(self.__dict__, f, indent=2)


class GEPATrainer:
    """Complete training pipeline for GEPA optimization."""

    def __init__(self, config: TrainingConfig):
        """Initialize trainer with configuration."""
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Setup RAG system
        print("Setting up RAG system...")
        self.rag_module, self.task_lm, self.metric_lm = setup_consilience_rag(
            db_url=config.db_url,
            openai_api_key=config.openai_api_key,
            pg_table_name=config.pg_table_name,
            use_multi_hop=config.use_multi_hop,
        )

        # Setup optimizer
        metric_func = (
            create_llm_metric(self.metric_lm)
            if config.use_llm_metric
            else create_simple_metric()
        )

        self.optimizer = GEPAOptimizer(
            task_model=self.task_lm,
            metric_model=self.metric_lm,
            reflection_lm=self.metric_lm,  # Use GPT-4 for reflection
            metric_func=metric_func,
            auto=config.gepa_auto,
            num_threads=config.gepa_num_threads,
            track_stats=config.gepa_track_stats,
            use_merge=config.gepa_use_merge,
            use_gepa=config.use_gepa,
        )

        # Data will be loaded during training
        self.data_splits = None
        self.optimized_module = None

    def load_data(self):
        """Load and prepare training data."""
        print(f"Loading data from {self.config.data_path}...")
        dataset = load_training_data(self.config.data_path)

        print(f"Loaded {len(dataset)} examples")
        print("Splitting dataset...")

        self.data_splits = prepare_dataset_splits(
            dataset,
            train_ratio=self.config.train_ratio,
            val_ratio=self.config.val_ratio,
            test_ratio=self.config.test_ratio,
        )

        print(f"Train: {len(self.data_splits['train'])} examples")
        print(f"Val: {len(self.data_splits['val'])} examples")
        print(f"Test: {len(self.data_splits['test'])} examples")

    def train(self):
        """Run GEPA optimization."""
        if self.data_splits is None:
            self.load_data()

        print("\n" + "="*80)
        print("Starting GEPA Optimization")
        print("="*80)

        # Optimize
        self.optimized_module = optimize_consilience_rag(
            rag_module=self.rag_module,
            task_lm=self.task_lm,
            metric_lm=self.metric_lm,
            trainset=self.data_splits['train'],
            valset=self.data_splits['val'],
            num_trials=self.config.num_trials,
        )

        print("\nOptimization complete!")

    def evaluate(self, split: str = 'test') -> float:
        """
        Evaluate model on specified split.

        Args:
            split: Dataset split to evaluate ('train', 'val', or 'test')

        Returns:
            Average evaluation score
        """
        if self.data_splits is None:
            self.load_data()

        module = self.optimized_module if self.optimized_module else self.rag_module
        devset = self.data_splits[split]

        print(f"\n" + "="*80)
        print(f"Evaluating on {split} set ({len(devset)} examples)")
        print("="*80)

        score = self.optimizer.evaluate(
            program=module,
            devset=devset,
            num_threads=self.config.eval_threads,
            display_progress=True,
            display_table=5,
        )

        print(f"\n{split.capitalize()} Set Score: {score:.4f}")
        return score

    def save_model(self, model_name: Optional[str] = None):
        """
        Save optimized model.

        Args:
            model_name: Optional custom model name
        """
        if self.optimized_module is None:
            print("Warning: No optimized module to save. Run train() first.")
            return

        if model_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            model_name = f"gepa_rag_{timestamp}"

        model_path = self.output_dir / f"{model_name}.json"

        print(f"\nSaving model to {model_path}...")
        self.optimized_module.save(str(model_path))
        print("Model saved successfully!")

        # Also save configuration
        config_path = self.output_dir / f"{model_name}_config.json"
        self.config.to_json(str(config_path))
        print(f"Configuration saved to {config_path}")

    def load_model(self, model_path: str):
        """
        Load pre-trained model.

        Args:
            model_path: Path to saved model
        """
        print(f"Loading model from {model_path}...")

        # Determine module type
        if self.config.use_multi_hop:
            self.optimized_module = MultiHopRAG()
        else:
            self.optimized_module = BasicRAG()

        self.optimized_module.load(model_path)
        print("Model loaded successfully!")

    def run_inference(self, question: str, verbose: bool = True) -> Dict[str, Any]:
        """
        Run inference on a single question.

        Args:
            question: Question to answer
            verbose: Whether to print results

        Returns:
            Dictionary with answer, keywords, and context
        """
        module = self.optimized_module if self.optimized_module else self.rag_module

        if verbose:
            print(f"\nQuestion: {question}")

        result = module(question=question)

        if verbose:
            print(f"\nAnswer: {result.answer}")
            print(f"\nKeywords: {result.keywords}")

        return {
            'question': question,
            'answer': result.answer,
            'keywords': result.keywords,
            'context': result.context if hasattr(result, 'context') else None,
        }

    def benchmark_comparison(self):
        """Compare optimized vs unoptimized models."""
        if self.data_splits is None:
            self.load_data()

        print("\n" + "="*80)
        print("Benchmark: Optimized vs Unoptimized")
        print("="*80)

        # Evaluate unoptimized
        print("\n--- Unoptimized Model ---")
        unoptimized_score = self.optimizer.evaluate(
            program=self.rag_module,
            devset=self.data_splits['test'],
            num_threads=self.config.eval_threads,
            display_progress=True,
            display_table=3,
        )

        # Evaluate optimized
        if self.optimized_module:
            print("\n--- Optimized Model ---")
            optimized_score = self.optimizer.evaluate(
                program=self.optimized_module,
                devset=self.data_splits['test'],
                num_threads=self.config.eval_threads,
                display_progress=True,
                display_table=3,
            )

            improvement = (optimized_score - unoptimized_score) / unoptimized_score * 100

            print("\n" + "="*80)
            print("RESULTS")
            print("="*80)
            print(f"Unoptimized Score: {unoptimized_score:.4f}")
            print(f"Optimized Score:   {optimized_score:.4f}")
            print(f"Improvement:       {improvement:+.2f}%")
        else:
            print("\nNo optimized model available. Run train() first.")


# ============================================================================
# CLI Interface
# ============================================================================

def create_default_config() -> TrainingConfig:
    """Create default training configuration."""
    return TrainingConfig(
        db_url=os.getenv("DATABASE_URL", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        data_path="./data/training_data.json",
        output_dir="./gepa_outputs",
        use_multi_hop=True,
        use_gepa=True,
        gepa_auto="light",  # Use "heavy" for better performance
        gepa_num_threads=1,
        gepa_track_stats=True,
        num_trials=30,
    )


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="GEPA Training Pipeline for Consilience RAG"
    )

    # Configuration
    parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration JSON file"
    )
    parser.add_argument(
        "--data",
        type=str,
        help="Path to training data JSON file"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./gepa_outputs",
        help="Output directory for models and results"
    )

    # Actions
    parser.add_argument(
        "--train",
        action="store_true",
        help="Run GEPA optimization"
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Evaluate model"
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Compare optimized vs unoptimized"
    )
    parser.add_argument(
        "--save-model",
        action="store_true",
        help="Save optimized model"
    )
    parser.add_argument(
        "--load-model",
        type=str,
        help="Load pre-trained model from path"
    )

    # Inference
    parser.add_argument(
        "--query",
        type=str,
        help="Run inference on a single question"
    )

    # Training parameters
    parser.add_argument(
        "--multi-hop",
        action="store_true",
        default=True,
        help="Use multi-hop RAG"
    )
    parser.add_argument(
        "--num-trials",
        type=int,
        default=30,
        help="Number of optimization trials"
    )

    args = parser.parse_args()

    # Load or create configuration
    if args.config:
        config = TrainingConfig.from_json(args.config)
    else:
        config = create_default_config()
        if args.data:
            config.data_path = args.data
        if args.output_dir:
            config.output_dir = args.output_dir
        config.use_multi_hop = args.multi_hop
        config.num_trials = args.num_trials

    # Validate configuration
    if not config.db_url or not config.openai_api_key:
        print("Error: DATABASE_URL and OPENAI_API_KEY must be set")
        print("Set them as environment variables or in config file")
        return

    # Initialize trainer
    trainer = GEPATrainer(config)

    # Load model if specified
    if args.load_model:
        trainer.load_model(args.load_model)

    # Execute actions
    if args.train:
        trainer.train()

    if args.evaluate:
        trainer.evaluate(split='test')

    if args.benchmark:
        trainer.benchmark_comparison()

    if args.save_model:
        trainer.save_model()

    if args.query:
        trainer.run_inference(args.query)

    # Default action: show help
    if not any([args.train, args.evaluate, args.benchmark, args.save_model, args.query]):
        parser.print_help()


if __name__ == "__main__":
    main()
