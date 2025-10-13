# GEPA-Optimized RAG System for Consilience

This directory contains an improved Retrieval Augmented Generation (RAG) system using DSPy with GEPA (Genetic-Pareto) optimizer. The system self-improves based on few-shot examples from the Digest API.

## Overview

The GEPA RAG system provides:

- **Self-improving prompts**: Automatically optimizes instructions through iterative refinement
- **Multi-hop retrieval**: Performs iterative searches to gather comprehensive context
- **Quality metrics**: LLM-based evaluation across multiple dimensions (detail, faithfulness, accuracy)
- **Keyword generation**: Structured metadata keywords for postgres full-text search
- **Few-shot learning**: Learns from high-quality examples to improve performance

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     GEPA Training Pipeline                   │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Training   │───▶│     GEPA     │───▶│  Optimized   │  │
│  │     Data     │    │  Optimizer   │    │     Model    │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                    │                    │          │
│         │                    ▼                    │          │
│         │           ┌─────────────────┐           │          │
│         │           │  LLM Evaluator  │           │          │
│         │           │  (GPT-4 Metric) │           │          │
│         │           └─────────────────┘           │          │
│         ▼                                          ▼          │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
        ┌─────────────────────────────────────────┐
        │         Runtime Inference               │
        ├─────────────────────────────────────────┤
        │                                          │
        │  Question → Multi-hop RAG → Answer      │
        │              ↓         ↓                 │
        │          PgVector   Keywords            │
        │          Retrieval                       │
        │                                          │
        └─────────────────────────────────────────┘
```

## Files

### Core Modules

- **`dspy_rag_system.py`**: Main RAG system implementation
  - `PgVectorRM`: PostgreSQL pgvector retriever
  - `BasicRAG`: Single-hop RAG module
  - `MultiHopRAG`: Multi-hop RAG with iterative retrieval
  - `GEPAOptimizer`: GEPA optimization engine
  - Evaluation metrics and signatures

- **`gepa_training_pipeline.py`**: Complete training pipeline
  - `TrainingConfig`: Configuration management
  - `GEPATrainer`: End-to-end training orchestration
  - Data loading and preparation
  - Model evaluation and benchmarking

### Examples

- **`examples/prepare_training_data.py`**: Prepare training data
  - Fetch from database
  - Create synthetic examples
  - Quality filtering

- **`examples/train_gepa_rag.py`**: Training example
  - Full training workflow
  - Baseline vs optimized comparison
  - Model saving and evaluation

## Installation

```bash
# Install required packages
pip install dspy-ai psycopg2 pgvector openai

# Or install from requirements
pip install -r requirements.txt
```

## Quick Start

### 1. Prepare Training Data

```bash
cd api_service
python examples/prepare_training_data.py \
  --output ./data/training_data.json \
  --limit 50
```

This creates a training dataset from:
- Historical Digest API responses (fetched from database)
- High-quality synthetic examples
- Filtered and deduplicated examples

### 2. Train the Model

```bash
python examples/train_gepa_rag.py
```

Or use the CLI:

```bash
python gepa_training_pipeline.py \
  --data ./data/training_data.json \
  --train \
  --evaluate \
  --save-model
```

### 3. Use the Optimized Model

```python
from dspy_rag_system import setup_consilience_rag
from gepa_training_pipeline import GEPATrainer, TrainingConfig

# Setup
config = TrainingConfig(
    db_url=os.getenv("DATABASE_URL"),
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    data_path="./data/training_data.json",
)

trainer = GEPATrainer(config)
trainer.load_model("./gepa_outputs/gepa_rag_optimized.json")

# Run inference
result = trainer.run_inference("What genes are related to diabetes?")
print(f"Answer: {result['answer']}")
print(f"Keywords: {result['keywords']}")
```

## Configuration

### Training Configuration

Create a `config.json`:

```json
{
  "db_url": "postgresql://user:pass@localhost:5432/consilience",
  "openai_api_key": "sk-...",
  "data_path": "./data/training_data.json",
  "output_dir": "./gepa_outputs",
  "pg_table_name": "document_chunks",
  "use_multi_hop": true,
  "num_trials": 30,
  "max_bootstrapped_demos": 4,
  "max_labeled_demos": 8,
  "num_candidates": 10,
  "train_ratio": 0.7,
  "val_ratio": 0.15,
  "test_ratio": 0.15,
  "use_llm_metric": true,
  "eval_threads": 1
}
```

Then run:

```bash
python gepa_training_pipeline.py --config config.json --train --evaluate
```

### Environment Variables

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/consilience"
export OPENAI_API_KEY="sk-..."
```

## CLI Reference

### Training Pipeline

```bash
# Full training pipeline
python gepa_training_pipeline.py \
  --data ./data/training_data.json \
  --train \
  --evaluate \
  --benchmark \
  --save-model

# Load and evaluate existing model
python gepa_training_pipeline.py \
  --load-model ./gepa_outputs/model.json \
  --evaluate

# Single query inference
python gepa_training_pipeline.py \
  --load-model ./gepa_outputs/model.json \
  --query "What are diabetes-related genes?"

# Custom configuration
python gepa_training_pipeline.py \
  --config ./config.json \
  --multi-hop \
  --num-trials 50 \
  --train
```

### Data Preparation

```bash
# Prepare from database
python examples/prepare_training_data.py \
  --output ./data/training_data.json \
  --db-url $DATABASE_URL \
  --limit 100

# Only synthetic examples
python examples/prepare_training_data.py \
  --output ./data/synthetic.json \
  --no-db

# Only from database
python examples/prepare_training_data.py \
  --output ./data/db_only.json \
  --no-synthetic \
  --limit 200
```

## Training Process

The GEPA training process follows these steps:

1. **Data Preparation**
   - Load training data from JSON
   - Split into train/validation/test sets (70/15/15)
   - Prepare few-shot examples

2. **Baseline Evaluation**
   - Evaluate unoptimized RAG system
   - Measure performance on validation set
   - Establish baseline metrics

3. **GEPA Optimization**
   - Use MIPRO optimizer from DSPy
   - Generate candidate prompts (default: 10 candidates)
   - Run optimization trials (default: 30 trials)
   - Bootstrap few-shot demonstrations (max: 4)
   - Use labeled demonstrations (max: 8)

4. **Evaluation**
   - Assess with LLM-based metrics (GPT-4)
   - Measure: detail, faithfulness, overall quality, keyword format
   - Compare optimized vs baseline

5. **Model Saving**
   - Save optimized prompts and demonstrations
   - Save configuration for reproducibility

## Evaluation Metrics

### LLM-Based Metric

Uses GPT-4 to evaluate answers across four dimensions:

1. **Detail** (1-5): Is the answer comprehensive and detailed?
2. **Faithfulness** (1-5): Is the answer grounded in retrieved context?
3. **Overall Quality** (1-5): How well does it answer the question?
4. **Keyword Format** (1-5): Are keywords properly formatted?

Total score: Average of all dimensions (normalized to 0-1)

### Simple Metric

Heuristic-based evaluation:
- Answer length (>100 chars: +0.5, >200 chars: +0.25)
- Keyword format (has `|`: +0.125, no spaces: +0.125)

## Integration with Consilience

### Replace Existing Query Endpoint

```python
# In api_service/app.py or similar
from dspy_rag_system import setup_consilience_rag

# Setup optimized RAG
rag_module, task_lm, metric_lm = setup_consilience_rag(
    db_url=os.getenv("DATABASE_URL"),
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    use_multi_hop=True,
)

# Load optimized model
rag_module.load("./gepa_outputs/gepa_rag_optimized.json")

@app.post("/query")
async def query(request: QueryRequest):
    result = rag_module(question=request.query)
    return {
        "answer": result.answer,
        "keywords": result.keywords.split("|"),
        "context": [{"text": p.long_text} for p in result.context],
    }
```

### Continuous Improvement

Set up periodic retraining:

```python
# Schedule daily/weekly retraining
from apscheduler.schedulers.background import BackgroundScheduler

def retrain_model():
    """Retrain with latest query data."""
    # Fetch recent high-quality queries
    prepare_training_data(
        db_url=os.getenv("DATABASE_URL"),
        fetch_from_db=True,
        db_limit=100,
    )

    # Retrain
    trainer = GEPATrainer(config)
    trainer.train()
    trainer.save_model()

scheduler = BackgroundScheduler()
scheduler.add_job(retrain_model, 'cron', day_of_week='sun', hour=2)
scheduler.start()
```

## Advanced Usage

### Custom Signatures

Define custom DSPy signatures for domain-specific tasks:

```python
class GenerateCitation(dspy.Signature):
    """Generate proper citations from context."""
    context = dspy.InputField(desc="Source documents")
    answer = dspy.InputField(desc="Generated answer")
    citations = dspy.OutputField(desc="Formatted citations")

# Use in RAG module
self.generate_citations = dspy.ChainOfThought(GenerateCitation)
```

### Custom Metrics

Create domain-specific evaluation metrics:

```python
def accuracy_metric(gold, pred, trace=None):
    """Check if answer contains expected entities."""
    expected_entities = set(gold.entities)
    predicted_text = pred.answer.lower()

    found = sum(1 for e in expected_entities if e.lower() in predicted_text)
    return found / len(expected_entities)

optimizer = GEPAOptimizer(
    task_model=task_lm,
    metric_model=metric_lm,
    metric_func=accuracy_metric,
)
```

### Multi-Stage Optimization

Optimize different components separately:

```python
# Stage 1: Optimize retrieval queries
query_optimizer = GEPAOptimizer(...)
optimized_query_gen = query_optimizer.optimize(
    program=GenerateSearchQuery(),
    trainset=query_trainset,
)

# Stage 2: Optimize answer generation
answer_optimizer = GEPAOptimizer(...)
optimized_answerer = answer_optimizer.optimize(
    program=GenerateAnswer(),
    trainset=answer_trainset,
)

# Combine
class OptimizedRAG(dspy.Module):
    def __init__(self):
        self.retrieve = dspy.Retrieve()
        self.query_gen = optimized_query_gen
        self.answerer = optimized_answerer
```

## Performance Tips

1. **Start Small**: Begin with 10-20 trials, increase if needed
2. **Use Validation Set**: Essential for avoiding overfitting
3. **Quality Over Quantity**: 20 high-quality examples > 100 poor ones
4. **GPU Acceleration**: Use GPU for faster OpenAI API calls
5. **Caching**: DSPy caches LM calls, reuse when possible
6. **Parallel Evaluation**: Increase `eval_threads` for faster evaluation

## Troubleshooting

### Low Performance

- Check training data quality
- Increase `num_trials`
- Try different `num_candidates`
- Use more few-shot examples

### Out of Memory

- Reduce `max_bootstrapped_demos`
- Decrease `num_candidates`
- Use smaller validation set

### Slow Training

- Reduce `num_trials`
- Use simpler metric (not LLM-based)
- Increase `eval_threads`
- Cache LM responses

## References

- [DSPy Documentation](https://dspy-docs.vercel.app/)
- [GEPA Tutorial](https://dspy.ai/tutorials/gepa_facilitysupportanalyzer/)
- [DSPy GitHub](https://github.com/stanfordnlp/dspy)
- Original notebook: `api_service/digest_api_data_analysis.ipynb`
- Original retriever: `api_service/retrievers/pgvector.py`

## Citation

If you use this system, please cite:

```bibtex
@software{consilience_gepa_rag,
  title = {GEPA-Optimized RAG System for Consilience},
  author = {Consilience Team},
  year = {2025},
  note = {Based on DSPy and GEPA optimizer}
}
```

## License

Same as parent Consilience project.
