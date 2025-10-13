"""
DSPy-based RAG System with GEPA Optimization for Consilience

This module implements an improved Retrieval Augmented Generation (RAG) system
using DSPy with GEPA (Genetic-Pareto) optimizer for
self-improvement based on few-shot examples.

Based on:
- api_service/retrievers/pgvector.py
- api_service/digest_api_data_analysis.ipynb
- https://dspy.ai/tutorials/gepa_facilitysupportanalyzer/
"""

import os
import warnings
from typing import List, Optional, Dict, Any, Callable

import dspy
try:
    from dspy import GEPA
    GEPA_AVAILABLE = True
except ImportError:
    # Fallback to MIPRO if GEPA not available in this DSPy version
    from dspy.teleprompt import MIPRO
    GEPA_AVAILABLE = False
from dspy.evaluate import Evaluate

try:
    import psycopg2
    from pgvector.psycopg2 import register_vector
    from psycopg2 import sql
except ImportError:
    raise ImportError(
        "Required packages missing. Install with: pip install psycopg2 pgvector"
    )

try:
    import openai
except ImportError:
    warnings.warn(
        "`openai` not installed. Install with `pip install openai`",
        category=ImportWarning,
    )


# ============================================================================
# DSPy Signatures
# ============================================================================

class GenerateAnswer(dspy.Signature):
    """Generate detailed, grounded answers based on retrieved context."""

    context = dspy.InputField(desc="Retrieved passages containing relevant facts")
    question = dspy.InputField(desc="User's question to answer")
    answer = dspy.OutputField(
        desc="Comprehensive answer grounded in context. Must be detailed, "
        "accurate, and cite specific facts from the context."
    )


class GenerateKeywords(dspy.Signature):
    """Generate structured keywords for metadata search."""

    context = dspy.InputField(desc="Retrieved passages with relevant information")
    question = dspy.InputField(desc="User's question")
    keywords = dspy.OutputField(
        desc="10 keywords for postgres full-text search. Format: keyword1|keyword2|"
        "multi&word&phrase|keyword3. Use | to separate keywords and & to replace "
        "spaces in multi-word phrases. Extract named entities and key concepts."
    )


class GenerateSearchQuery(dspy.Signature):
    """Generate an improved search query to retrieve more relevant context."""

    context = dspy.InputField(desc="Previously retrieved context")
    question = dspy.InputField(desc="Original user question")
    search_query = dspy.OutputField(
        desc="Refined search query that will retrieve additional relevant context. "
        "Should be different from the original question and focus on key concepts."
    )


class Assess(dspy.Signature):
    """Assess the quality of an answer to a question."""

    context = dspy.InputField(desc="Context used for answering")
    assessed_question = dspy.InputField(desc="The evaluation criterion")
    assessed_answer = dspy.InputField(desc="The answer being evaluated")
    assessment_answer = dspy.OutputField(
        desc="Rating between 1 and 5. Only output the rating number."
    )


class AssessKeyword(dspy.Signature):
    """Assess keyword quality for metadata search."""

    context = dspy.InputField(desc="Context for the question")
    assessed_question = dspy.InputField(desc="Evaluation criterion")
    assessed_keywords = dspy.InputField(desc="Generated keywords")
    assessment_answer = dspy.OutputField(
        desc="Rating between 1 and 5. Only output the rating number."
    )


# ============================================================================
# DSPy Retriever Module
# ============================================================================

class PgVectorRM(dspy.Retrieve):
    """
    PgVector retriever for DSPy that connects to PostgreSQL with pgvector.

    Performs vector similarity search using cosine distance to retrieve
    relevant document chunks based on query embeddings.
    """

    def __init__(
        self,
        db_url: str,
        pg_table_name: str,
        openai_client: Optional[openai.OpenAI] = None,
        embedding_func: Optional[Callable] = None,
        k: int = 20,
        embedding_field: str = "embedding",
        fields: Optional[List[str]] = None,
        content_field: str = "text",
        embedding_model: str = "text-embedding-ada-002",
        include_similarity: bool = False,
    ):
        """
        Initialize PgVector retriever.

        Args:
            db_url: PostgreSQL connection URL
            pg_table_name: Table containing document chunks
            openai_client: OpenAI client for embeddings
            embedding_func: Custom embedding function
            k: Number of passages to retrieve
            embedding_field: Name of embedding column
            fields: Fields to retrieve from table
            content_field: Field containing text content
            embedding_model: OpenAI embedding model to use
            include_similarity: Whether to include similarity scores
        """
        assert (
            openai_client or embedding_func
        ), "Either openai_client or embedding_func must be provided"

        self.openai_client = openai_client
        self.embedding_func = embedding_func
        self.conn = psycopg2.connect(db_url)
        register_vector(self.conn)

        self.pg_table_name = pg_table_name
        self.fields = fields or ["text"]
        self.content_field = content_field
        self.embedding_field = embedding_field
        self.embedding_model = embedding_model
        self.include_similarity = include_similarity

        super().__init__(k=k)

    def forward(self, query: str, k: Optional[int] = None) -> List[dspy.Example]:
        """
        Retrieve top-k passages for query using cosine similarity.

        Args:
            query: Search query
            k: Number of passages to retrieve (overrides default)

        Returns:
            List of dspy.Example objects with retrieved passages
        """
        query_embedding = self._get_embeddings(query)
        retrieved_docs = []

        # Build SQL query
        fields = sql.SQL(",").join([sql.Identifier(f) for f in self.fields])
        if self.include_similarity:
            similarity_field = sql.SQL(",") + sql.SQL(
                "1 - ({embedding_field} <=> %s::vector) AS similarity"
            ).format(embedding_field=sql.Identifier(self.embedding_field))
            fields += similarity_field
            args = (query_embedding, query_embedding, k if k else self.k)
        else:
            args = (query_embedding, k if k else self.k)

        sql_query = sql.SQL(
            "SELECT {fields} FROM {table} ORDER BY {embedding_field} <=> %s::vector LIMIT %s"
        ).format(
            fields=fields,
            table=sql.Identifier(self.pg_table_name),
            embedding_field=sql.Identifier(self.embedding_field),
        )

        # Execute query
        with self.conn as conn:
            with conn.cursor() as cur:
                cur.execute(sql_query, args)
                rows = cur.fetchall()
                columns = [desc[0] for desc in cur.description]
                for row in rows:
                    data = dict(zip(columns, row))
                    data["long_text"] = data[self.content_field]
                    retrieved_docs.append(dspy.Example(**data))

        return retrieved_docs

    def _get_embeddings(self, query: str) -> List[float]:
        """Generate embeddings for query."""
        if self.openai_client is not None:
            return (
                self.openai_client.embeddings.create(
                    model=self.embedding_model,
                    input=query,
                    encoding_format="float",
                )
                .data[0]
                .embedding
            )
        else:
            return self.embedding_func(query)


# ============================================================================
# DSPy RAG Modules
# ============================================================================

class BasicRAG(dspy.Module):
    """
    Basic RAG module with single-hop retrieval.

    Retrieves relevant passages and generates an answer with keywords.
    """

    def __init__(self, num_passages: int = 20):
        """
        Initialize BasicRAG module.

        Args:
            num_passages: Number of passages to retrieve
        """
        super().__init__()
        self.retrieve = dspy.Retrieve(k=num_passages)
        self.generate_answer = dspy.ChainOfThought(GenerateAnswer)
        self.generate_keywords = dspy.ChainOfThought(GenerateKeywords)

    def forward(self, question: str) -> dspy.Prediction:
        """
        Process question and generate answer with keywords.

        Args:
            question: User's question

        Returns:
            Prediction with answer and keywords
        """
        context = self.retrieve(question).passages
        answer_pred = self.generate_answer(context=context, question=question)
        keywords_pred = self.generate_keywords(context=context, question=question)

        return dspy.Prediction(
            answer=answer_pred.answer,
            keywords=keywords_pred.keywords,
            context=context
        )


class MultiHopRAG(dspy.Module):
    """
    Multi-hop RAG with iterative retrieval refinement.

    Performs multiple retrieval steps to gather comprehensive context
    before generating the final answer.
    """

    def __init__(self, passages_per_hop: int = 10, num_hops: int = 2):
        """
        Initialize MultiHopRAG module.

        Args:
            passages_per_hop: Passages to retrieve per hop
            num_hops: Number of retrieval hops
        """
        super().__init__()
        self.num_hops = num_hops
        self.retrieve = dspy.Retrieve(k=passages_per_hop)
        self.generate_query = dspy.ChainOfThought(GenerateSearchQuery)
        self.generate_answer = dspy.ChainOfThought(GenerateAnswer)
        self.generate_keywords = dspy.ChainOfThought(GenerateKeywords)

    def forward(self, question: str) -> dspy.Prediction:
        """
        Process question with multi-hop retrieval.

        Args:
            question: User's question

        Returns:
            Prediction with answer and keywords
        """
        context = []

        # Multi-hop retrieval
        for hop in range(self.num_hops):
            if hop == 0:
                query = question
            else:
                query = self.generate_query(
                    context=context, question=question
                ).search_query

            new_passages = self.retrieve(query).passages
            context.extend(new_passages)

        # Generate answer and keywords
        answer_pred = self.generate_answer(context=context, question=question)
        keywords_pred = self.generate_keywords(context=context, question=question)

        return dspy.Prediction(
            answer=answer_pred.answer,
            keywords=keywords_pred.keywords,
            context=context
        )


# ============================================================================
# Evaluation Metrics
# ============================================================================

def create_llm_metric(metric_lm: dspy.LM) -> Callable:
    """
    Create an LLM-based evaluation metric.

    Uses a language model (typically GPT-4) to assess answer quality
    across multiple dimensions: detail, faithfulness, overall quality,
    and keyword correctness.

    Args:
        metric_lm: Language model for evaluation

    Returns:
        Evaluation function
    """

    def llm_metric(gold: dspy.Example, pred: dspy.Example, trace=None) -> float:
        """
        Evaluate prediction against gold standard.

        Args:
            gold: Gold standard example with expected outputs
            pred: Predicted outputs
            trace: Optional execution trace

        Returns:
            Score between 0 and 1
        """
        predicted_answer = pred.answer
        question = gold.question
        keywords = pred.keywords if hasattr(pred, 'keywords') else ""

        # Evaluation criteria
        detail_q = "Is the assessed answer detailed?"
        faithful_q = (
            "Is the assessed text grounded in the context? "
            "Rate 1 if it includes significant facts not in the context, "
            "5 if it is fully grounded in the context."
        )
        overall_q = (
            f"Based on the context, rate how well this answer responds to: "
            f"'{question}'"
        )
        keyword_q = (
            "Are the keywords properly formatted with | separators and & for spaces? "
            "Rate 1 if poorly formatted, 5 if perfect."
        )

        # Get context
        context = pred.context if hasattr(pred, 'context') else []

        # Evaluate with metric LM
        with dspy.context(lm=metric_lm):
            detail = dspy.ChainOfThought(Assess)(
                context=context,
                assessed_question=detail_q,
                assessed_answer=predicted_answer
            )
            faithful = dspy.ChainOfThought(Assess)(
                context=context,
                assessed_question=faithful_q,
                assessed_answer=predicted_answer
            )
            overall = dspy.ChainOfThought(Assess)(
                context=context,
                assessed_question=overall_q,
                assessed_answer=predicted_answer
            )
            keyword = dspy.ChainOfThought(AssessKeyword)(
                context=context,
                assessed_question=keyword_q,
                assessed_keywords=keywords
            )

        # Calculate total score
        try:
            detail_score = float(detail.assessment_answer)
            faithful_score = float(faithful.assessment_answer)
            overall_score = float(overall.assessment_answer)
            keyword_score = float(keyword.assessment_answer)

            total = detail_score + faithful_score + overall_score + keyword_score
            return total / 20.0  # Normalize to 0-1
        except (ValueError, AttributeError):
            return 0.0

    return llm_metric


def create_simple_metric() -> Callable:
    """
    Create a simple heuristic-based evaluation metric.

    Returns:
        Evaluation function
    """

    def simple_metric(gold: dspy.Example, pred: dspy.Example, trace=None) -> float:
        """
        Simple evaluation based on answer length and keyword format.

        Args:
            gold: Gold standard example
            pred: Predicted outputs
            trace: Optional execution trace

        Returns:
            Score between 0 and 1
        """
        score = 0.0

        # Check answer exists and has reasonable length
        if hasattr(pred, 'answer') and pred.answer:
            if len(pred.answer) > 100:
                score += 0.5
            if len(pred.answer) > 200:
                score += 0.25

        # Check keywords format
        if hasattr(pred, 'keywords') and pred.keywords:
            keywords = pred.keywords
            # Check for | separator
            if '|' in keywords:
                score += 0.125
            # Check no spaces (should use &)
            if ' ' not in keywords or '&' in keywords:
                score += 0.125

        return score

    return simple_metric


# ============================================================================
# GEPA Optimization Pipeline
# ============================================================================

class GEPAOptimizer:
    """
    GEPA (Genetic-Pareto) Optimizer for RAG.

    GEPA is a reflective prompt evolution optimizer that uses LLM reflection
    on execution traces to iteratively improve prompts. It maintains a Pareto
    front of solutions and uses natural language feedback to drive targeted
    improvements.

    Based on: "GEPA: Reflective Prompt Evolution Can Outperform Reinforcement
    Learning" (https://arxiv.org/abs/2507.19457)

    If GEPA is not available in your DSPy version, falls back to MIPRO.
    """

    def __init__(
        self,
        task_model: dspy.LM,
        metric_model: dspy.LM,
        metric_func: Optional[Callable] = None,
        auto: str = "light",
        num_threads: int = 1,
        track_stats: bool = True,
        use_merge: bool = False,
        reflection_lm: Optional[dspy.LM] = None,
        use_gepa: bool = True,
    ):
        """
        Initialize GEPA optimizer.

        Args:
            task_model: Language model for RAG tasks
            metric_model: Language model for evaluation
            metric_func: Custom metric function with feedback
            auto: Budget mode - "light" (faster) or "heavy" (better performance)
            num_threads: Number of parallel threads for optimization
            track_stats: Whether to track optimization statistics
            use_merge: Whether to use merge operations
            reflection_lm: LM for reflection (typically stronger model like GPT-4/GPT-5)
            use_gepa: Whether to use GEPA (if available) or fall back to MIPRO
        """
        self.task_model = task_model
        self.metric_model = metric_model
        self.reflection_lm = reflection_lm or metric_model
        self.metric_func = metric_func or create_llm_metric(metric_model)
        self.auto = auto
        self.num_threads = num_threads
        self.track_stats = track_stats
        self.use_merge = use_merge
        self.use_gepa = use_gepa and GEPA_AVAILABLE

        if self.use_gepa:
            print(f"Using GEPA (Genetic-Pareto) optimizer with reflection [auto={auto}]")
        else:
            if not GEPA_AVAILABLE:
                print("GEPA not available, falling back to MIPRO optimizer")
            else:
                print("Using MIPRO optimizer (GEPA disabled)")

    def optimize(
        self,
        program: dspy.Module,
        trainset: List[dspy.Example],
        valset: Optional[List[dspy.Example]] = None,
        num_trials: int = 30,
        max_bootstrapped_demos: int = 4,
        max_labeled_demos: int = 8,
    ) -> dspy.Module:
        """
        Optimize RAG program using GEPA or MIPRO.

        Args:
            program: RAG module to optimize
            trainset: Training examples with questions and expected outputs
            valset: Optional validation set
            num_trials: Number of optimization trials (MIPRO only)
            max_bootstrapped_demos: Max few-shot demos to bootstrap (MIPRO only)
            max_labeled_demos: Max labeled demos to use (MIPRO only)

        Returns:
            Optimized RAG module
        """
        # Configure DSPy
        dspy.settings.configure(lm=self.task_model)

        if self.use_gepa:
            # Use GEPA optimizer with reflection
            print(f"Starting GEPA optimization [auto={self.auto}, threads={self.num_threads}]...")
            optimizer = GEPA(
                metric=self.metric_func,
                auto=self.auto,
                num_threads=self.num_threads,
                track_stats=self.track_stats,
                use_merge=self.use_merge,
                reflection_lm=self.reflection_lm,
            )

            optimized_program = optimizer.compile(
                program,
                trainset=trainset,
                valset=valset or trainset[:len(trainset)//5],  # Use 20% of train as val if not provided
            )
        else:
            # Fallback to MIPRO optimizer
            print(f"Starting MIPRO optimization with {num_trials} trials...")
            optimizer = MIPRO(
                metric=self.metric_func,
                num_candidates=10,
                init_temperature=1.0,
            )

            optimized_program = optimizer.compile(
                program,
                trainset=trainset,
                valset=valset,
                num_trials=num_trials,
                max_bootstrapped_demos=max_bootstrapped_demos,
                max_labeled_demos=max_labeled_demos,
            )

        print("Optimization complete!")
        return optimized_program

    def evaluate(
        self,
        program: dspy.Module,
        devset: List[dspy.Example],
        num_threads: int = 1,
        display_progress: bool = True,
        display_table: int = 5,
    ) -> float:
        """
        Evaluate RAG program on development set.

        Args:
            program: RAG module to evaluate
            devset: Development/test examples
            num_threads: Number of parallel threads
            display_progress: Whether to show progress bar
            display_table: Number of examples to display

        Returns:
            Average score
        """
        evaluator = Evaluate(
            devset=devset,
            metric=self.metric_func,
            num_threads=num_threads,
            display_progress=display_progress,
            display_table=display_table,
        )

        score = evaluator(program)
        return score


# ============================================================================
# Convenience Functions
# ============================================================================

def setup_consilience_rag(
    db_url: str,
    openai_api_key: str,
    pg_table_name: str = "document_chunks",
    embedding_field: str = "embedding",
    content_field: str = "text",
    use_multi_hop: bool = True,
) -> tuple[dspy.Module, dspy.LM, dspy.LM]:
    """
    Setup complete RAG system for Consilience.

    Args:
        db_url: PostgreSQL connection URL
        openai_api_key: OpenAI API key
        pg_table_name: Table with document chunks
        embedding_field: Embedding column name
        content_field: Text content column name
        use_multi_hop: Whether to use multi-hop RAG

    Returns:
        Tuple of (rag_module, task_lm, metric_lm)
    """
    # Initialize OpenAI client
    openai_client = openai.OpenAI(api_key=openai_api_key)

    # Initialize retriever
    retriever = PgVectorRM(
        db_url=db_url,
        pg_table_name=pg_table_name,
        openai_client=openai_client,
        k=20,
        embedding_field=embedding_field,
        content_field=content_field,
        fields=["text", "document_id"],
        include_similarity=True,
    )

    # Initialize language models
    task_lm = dspy.OpenAI(
        model="gpt-3.5-turbo",
        max_tokens=500,
        api_key=openai_api_key
    )
    metric_lm = dspy.OpenAI(
        model="gpt-4",
        max_tokens=1000,
        api_key=openai_api_key
    )

    # Configure DSPy
    dspy.settings.configure(lm=task_lm, rm=retriever)

    # Initialize RAG module
    if use_multi_hop:
        rag_module = MultiHopRAG(passages_per_hop=10, num_hops=2)
    else:
        rag_module = BasicRAG(num_passages=20)

    return rag_module, task_lm, metric_lm


def optimize_consilience_rag(
    rag_module: dspy.Module,
    task_lm: dspy.LM,
    metric_lm: dspy.LM,
    trainset: List[dspy.Example],
    valset: Optional[List[dspy.Example]] = None,
    num_trials: int = 30,
) -> dspy.Module:
    """
    Optimize Consilience RAG system with GEPA.

    Args:
        rag_module: RAG module to optimize
        task_lm: Task language model
        metric_lm: Metric language model
        trainset: Training examples
        valset: Optional validation examples
        num_trials: Number of optimization trials

    Returns:
        Optimized RAG module
    """
    optimizer = GEPAOptimizer(
        task_model=task_lm,
        metric_model=metric_lm,
        num_candidates=10,
        init_temperature=1.0,
    )

    optimized_rag = optimizer.optimize(
        program=rag_module,
        trainset=trainset,
        valset=valset,
        num_trials=num_trials,
        max_bootstrapped_demos=4,
        max_labeled_demos=8,
    )

    return optimized_rag


if __name__ == "__main__":
    # Example usage
    import sys

    # Get configuration from environment
    db_url = os.getenv("DATABASE_URL")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not db_url or not openai_api_key:
        print("Error: DATABASE_URL and OPENAI_API_KEY must be set")
        sys.exit(1)

    # Setup RAG system
    print("Setting up RAG system...")
    rag_module, task_lm, metric_lm = setup_consilience_rag(
        db_url=db_url,
        openai_api_key=openai_api_key,
        use_multi_hop=True,
    )

    # Test query
    test_question = "What are the main findings about diabetes genetics?"
    print(f"\nTest Question: {test_question}")

    result = rag_module(question=test_question)
    print(f"\nAnswer: {result.answer}")
    print(f"\nKeywords: {result.keywords}")
