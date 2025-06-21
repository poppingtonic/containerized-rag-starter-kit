# WriteHere-GraphRAG Evaluation System Roadmap

## Overview
This roadmap outlines the implementation of a comprehensive evaluation system for WriteHere-GraphRAG, inspired by the principles from ALIGN Eval. The system will progressively enhance quality assurance from document ingestion through to final answer generation.

## Phase 1: Document Ingestion Quality Evaluation (Week 1-2)

### 1.1 Chunk Quality Evaluator
**Goal:** Ensure document chunks are coherent and complete

**Implementation:**
```python
# New file: api_service/evaluators/chunk_quality.py
class ChunkQualityEvaluator:
    def evaluate_chunk(self, chunk: str) -> dict:
        """
        Binary evaluation criteria:
        - Is the chunk grammatically complete?
        - Does it contain meaningful information?
        - Is it free from excessive formatting artifacts?
        """
```

**Database Schema:**
```sql
-- Add to existing schema
CREATE TABLE chunk_evaluations (
    id SERIAL PRIMARY KEY,
    chunk_id INTEGER REFERENCES document_chunks(id),
    evaluation_criteria VARCHAR(100),
    score INTEGER CHECK (score IN (0, 1)),
    explanation TEXT,
    model_used VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chunk_evaluations_chunk_id ON chunk_evaluations(chunk_id);
CREATE INDEX idx_chunk_evaluations_criteria ON chunk_evaluations(evaluation_criteria);
```

**Integration Points:**
- Modify `ingestion_service/app.py` to run evaluations after chunk creation
- Add evaluation metrics to ingestion status endpoint
- Store evaluation results for monitoring

### 1.2 Document Completeness Checker
**Goal:** Verify successful document processing

**Metrics:**
- OCR success rate for scanned documents
- Chunk coverage (% of document successfully chunked)
- Metadata extraction completeness
- Duplicate detection accuracy

**API Endpoints:**
```python
# Add to api_service/app.py
@app.get("/ingestion/quality/{document_id}")
async def get_document_quality(document_id: int):
    """Return quality metrics for a specific document"""

@app.get("/ingestion/quality/summary")
async def get_ingestion_quality_summary():
    """Return aggregate quality metrics across all documents"""
```

## Phase 2: Retrieval Relevance Scoring System (Week 3-4)

### 2.1 Binary Relevance Evaluator
**Goal:** Score chunk relevance to queries

**Implementation:**
```python
# New file: api_service/evaluators/retrieval_relevance.py
class RetrievalRelevanceEvaluator:
    def __init__(self):
        self.prompt_template = """
        <sketchpad>
        Query: {query}
        Retrieved Chunk: {chunk}
        
        Evaluate if this chunk contains information relevant to answering the query.
        Consider:
        1. Does the chunk contain facts related to the query topic?
        2. Would this chunk help answer the query?
        3. Is the information in the chunk directly applicable?
        </sketchpad>
        
        Prediction: Return 1 if relevant, 0 if not relevant.
        """
    
    def evaluate_retrieval(self, query: str, chunk: str) -> dict:
        """Returns relevance score with explanation"""
```

**Database Schema:**
```sql
CREATE TABLE retrieval_evaluations (
    id SERIAL PRIMARY KEY,
    query_id INTEGER REFERENCES query_cache(id),
    chunk_id INTEGER REFERENCES document_chunks(id),
    relevance_score INTEGER CHECK (relevance_score IN (0, 1)),
    explanation TEXT,
    retrieval_method VARCHAR(50), -- 'vector', 'graph', 'hybrid'
    rank_position INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_retrieval_evaluations_query ON retrieval_evaluations(query_id);
```

### 2.2 Retrieval Comparison Framework
**Goal:** Compare different retrieval strategies

**Metrics:**
- Precision@K (K=5, 10)
- Recall@K
- Mean Reciprocal Rank (MRR)
- Graph enhancement impact score

**Implementation:**
```python
# Add to api_service/services/qa_service.py
class RetrievalEvaluator:
    def compare_retrieval_methods(self, query: str):
        """
        Run query through:
        1. Vector-only retrieval
        2. Graph-enhanced retrieval
        3. Hybrid approach
        
        Return comparative metrics
        """
```

## Phase 3: Citation Accuracy Evaluation (Week 5-6)

### 3.1 Citation Verifier
**Goal:** Ensure citations accurately support claims

**Implementation:**
```python
# New file: api_service/evaluators/citation_accuracy.py
class CitationAccuracyEvaluator:
    def __init__(self):
        self.prompt_template = """
        <sketchpad>
        Claim: {claim}
        Cited Source: {source_text}
        
        Evaluate if the cited source actually supports the claim.
        Consider:
        1. Does the source contain the information stated in the claim?
        2. Is the claim a fair representation of the source?
        3. Are there any distortions or hallucinations?
        </sketchpad>
        
        Prediction: Return 1 if citation is accurate, 0 if not.
        """
    
    def verify_citation(self, claim: str, source: str) -> dict:
        """Returns accuracy score with explanation"""
```

### 3.2 Answer Quality Evaluator
**Goal:** Comprehensive answer evaluation

**Criteria:**
- All claims have citations
- Citations are accurate (using CitationVerifier)
- Answer addresses the query completely
- No hallucinations present

**Database Schema:**
```sql
CREATE TABLE answer_evaluations (
    id SERIAL PRIMARY KEY,
    query_cache_id INTEGER REFERENCES query_cache(id),
    evaluation_type VARCHAR(50), -- 'citation_accuracy', 'completeness', 'hallucination'
    score INTEGER CHECK (score IN (0, 1)),
    explanation TEXT,
    details JSONB, -- Store claim-citation pairs and individual scores
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Phase 4: Evaluation Dashboard & Metrics (Week 7-8)

### 4.1 Real-time Metrics API
**Endpoints:**
```python
@app.get("/metrics/ingestion")
async def get_ingestion_metrics():
    """
    Returns:
    - Documents processed (24h, 7d, 30d)
    - Average chunk quality scores
    - OCR success rates
    - Processing times
    """

@app.get("/metrics/retrieval")
async def get_retrieval_metrics():
    """
    Returns:
    - Average precision@K
    - Graph enhancement impact
    - Retrieval latency
    - Cache hit rates
    """

@app.get("/metrics/answers")
async def get_answer_metrics():
    """
    Returns:
    - Citation accuracy rates
    - Answer completeness scores
    - User satisfaction (from feedback)
    - Response times
    """
```

### 4.2 Evaluation UI Components
**Frontend additions:**
```vue
<!-- New components in frontend/src/components/evaluation/ -->
<EvaluationDashboard>
  <IngestionMetrics />
  <RetrievalMetrics />
  <AnswerQualityMetrics />
  <TrendCharts />
</EvaluationDashboard>
```

## Phase 5: Semi-Automatic Optimization (Week 9-10)

### 5.1 Prompt Optimization Framework
**Goal:** Automatically improve evaluation and generation prompts

**Implementation:**
```python
# New file: api_service/optimizers/prompt_optimizer.py
class PromptOptimizer:
    def optimize_prompt(self, 
                       base_prompt: str,
                       labeled_examples: List[dict],
                       target_metric: str = 'f1'):
        """
        Run trials with prompt variations
        Select best performing prompt
        """
```

### 5.2 A/B Testing Infrastructure
**Features:**
- Test different retrieval strategies
- Compare answer generation approaches
- Automatic winner selection based on metrics

**Database Schema:**
```sql
CREATE TABLE ab_tests (
    id SERIAL PRIMARY KEY,
    test_name VARCHAR(100),
    variant_a JSONB,
    variant_b JSONB,
    metrics JSONB,
    winner VARCHAR(1),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
```

## Implementation Priority & Dependencies

### High Priority (Implement First)
1. **Chunk Quality Evaluator** - Foundation for all downstream quality
2. **Retrieval Relevance Scoring** - Critical for answer quality
3. **Citation Accuracy** - Core to system trustworthiness

### Medium Priority
4. **Evaluation Dashboard** - Visibility into system performance
5. **Semi-Automatic Optimization** - Continuous improvement

### Technical Dependencies
- OpenAI API for evaluations (consider adding Claude support)
- Additional database tables and indexes
- Frontend components for visualization
- Background job processing for batch evaluations

## Success Metrics

### Phase 1 Success
- 95%+ chunks pass quality evaluation
- <5% document processing failures
- Automated alerts for quality issues

### Phase 2 Success
- Precision@10 > 0.8 for relevance
- Graph enhancement shows measurable improvement
- Retrieval latency < 500ms p95

### Phase 3 Success
- Citation accuracy > 95%
- Zero hallucination rate
- User satisfaction > 4.5/5

### Phase 4 Success
- Real-time metrics available
- Historical trend analysis
- Actionable insights generated

### Phase 5 Success
- 10%+ improvement in key metrics through optimization
- Automated A/B test execution
- Self-improving system

## Next Steps

1. Review and approve roadmap
2. Set up evaluation database tables
3. Implement Phase 1 chunk quality evaluator
4. Begin collecting baseline metrics
5. Iterate based on initial results

This roadmap provides a systematic approach to building a comprehensive evaluation system that will continuously improve the quality and reliability of WriteHere-GraphRAG.