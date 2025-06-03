import json
from typing import List, Dict, Any, Optional
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
    context_relevancy,
    answer_similarity,
    answer_correctness
)
from datasets import Dataset
from langchain_openai import ChatOpenAI
from utils import Config

class RagasService:
    def __init__(self):
        # Initialize LLM for RAGAS evaluation
        self.llm = ChatOpenAI(
            openai_api_key=Config.OPENAI_API_KEY,
            model="gpt-4",
            temperature=0
        )
        
        # Define metrics to use
        self.metrics = [
            faithfulness,
            answer_relevancy,
            context_precision,
            context_relevancy,
        ]
    
    def evaluate_single(self, query: str, answer: str, contexts: List[str], 
                       ground_truth: Optional[str] = None) -> Dict[str, float]:
        """
        Evaluate a single query-answer pair using RAGAS metrics.
        
        Args:
            query: The user's question
            answer: The generated answer
            contexts: List of retrieved context chunks
            ground_truth: Optional ground truth answer for comparison
        
        Returns:
            Dictionary of metric scores
        """
        try:
            # Prepare data for RAGAS
            eval_data = {
                "question": [query],
                "answer": [answer],
                "contexts": [contexts],
            }
            
            # Add ground truth if provided
            if ground_truth:
                eval_data["ground_truth"] = [ground_truth]
                # Add context recall metric if we have ground truth
                if context_recall not in self.metrics:
                    metrics_with_recall = self.metrics + [context_recall, answer_correctness]
                else:
                    metrics_with_recall = self.metrics
            else:
                metrics_with_recall = self.metrics
            
            # Create dataset
            dataset = Dataset.from_dict(eval_data)
            
            # Run evaluation
            results = evaluate(
                dataset,
                metrics=metrics_with_recall,
                llm=self.llm
            )
            
            # Extract scores
            scores = {}
            for metric in metrics_with_recall:
                metric_name = metric.name
                if metric_name in results:
                    scores[metric_name] = float(results[metric_name])
            
            # Calculate overall score (average of all metrics)
            if scores:
                scores["overall_score"] = sum(scores.values()) / len(scores)
            
            return scores
            
        except Exception as e:
            print(f"Error in RAGAS evaluation: {e}")
            return {
                "error": str(e),
                "overall_score": 0.0
            }
    
    def evaluate_batch(self, queries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluate multiple query-answer pairs.
        
        Args:
            queries: List of dictionaries containing query, answer, and contexts
        
        Returns:
            Aggregated evaluation results
        """
        all_scores = []
        
        for item in queries:
            scores = self.evaluate_single(
                query=item["query"],
                answer=item["answer"],
                contexts=item.get("contexts", []),
                ground_truth=item.get("ground_truth")
            )
            all_scores.append(scores)
        
        # Aggregate results
        aggregated = self._aggregate_scores(all_scores)
        return aggregated
    
    def _aggregate_scores(self, scores_list: List[Dict[str, float]]) -> Dict[str, Any]:
        """Aggregate scores from multiple evaluations."""
        if not scores_list:
            return {}
        
        # Get all metric names
        metric_names = set()
        for scores in scores_list:
            metric_names.update(scores.keys())
        metric_names.discard("error")  # Remove error key if present
        
        # Calculate averages for each metric
        aggregated = {}
        for metric in metric_names:
            values = [s.get(metric, 0.0) for s in scores_list if metric in s and "error" not in s]
            if values:
                aggregated[f"{metric}_avg"] = sum(values) / len(values)
                aggregated[f"{metric}_min"] = min(values)
                aggregated[f"{metric}_max"] = max(values)
        
        # Count errors
        error_count = sum(1 for s in scores_list if "error" in s)
        if error_count > 0:
            aggregated["error_count"] = error_count
            aggregated["success_rate"] = (len(scores_list) - error_count) / len(scores_list)
        
        return aggregated
    
    def get_metric_explanations(self) -> Dict[str, str]:
        """Get human-readable explanations for each metric."""
        return {
            "faithfulness": "Measures how grounded the answer is in the provided context (0-1, higher is better)",
            "answer_relevancy": "Measures how relevant the answer is to the question (0-1, higher is better)",
            "context_precision": "Measures the signal-to-noise ratio of retrieved contexts (0-1, higher is better)",
            "context_relevancy": "Measures how relevant the retrieved contexts are to the question (0-1, higher is better)",
            "context_recall": "Measures how much of the ground truth is covered by contexts (requires ground truth)",
            "answer_correctness": "Measures factual accuracy compared to ground truth (requires ground truth)",
            "overall_score": "Average of all computed metrics (0-1, higher is better)"
        }
    
    def interpret_scores(self, scores: Dict[str, float]) -> Dict[str, Any]:
        """
        Interpret RAGAS scores and provide actionable insights.
        
        Returns:
            Dictionary with interpretation and recommendations
        """
        interpretation = {
            "quality_level": self._get_quality_level(scores.get("overall_score", 0)),
            "strengths": [],
            "weaknesses": [],
            "recommendations": []
        }
        
        # Analyze each metric
        for metric, value in scores.items():
            if metric == "error" or not isinstance(value, (int, float)):
                continue
                
            if value >= 0.8:
                interpretation["strengths"].append(f"{metric}: {value:.2f} (Excellent)")
            elif value >= 0.6:
                interpretation["strengths"].append(f"{metric}: {value:.2f} (Good)")
            elif value >= 0.4:
                interpretation["weaknesses"].append(f"{metric}: {value:.2f} (Fair)")
            else:
                interpretation["weaknesses"].append(f"{metric}: {value:.2f} (Poor)")
        
        # Add specific recommendations based on low scores
        if scores.get("faithfulness", 1.0) < 0.6:
            interpretation["recommendations"].append(
                "Improve answer grounding: Ensure answers strictly use information from retrieved contexts"
            )
        
        if scores.get("answer_relevancy", 1.0) < 0.6:
            interpretation["recommendations"].append(
                "Improve answer relevance: Focus on directly addressing the user's question"
            )
        
        if scores.get("context_precision", 1.0) < 0.6:
            interpretation["recommendations"].append(
                "Improve retrieval precision: Too many irrelevant chunks are being retrieved"
            )
        
        if scores.get("context_relevancy", 1.0) < 0.6:
            interpretation["recommendations"].append(
                "Improve retrieval relevance: Retrieved contexts don't match the query well"
            )
        
        return interpretation
    
    def _get_quality_level(self, overall_score: float) -> str:
        """Convert overall score to quality level."""
        if overall_score >= 0.8:
            return "Excellent"
        elif overall_score >= 0.6:
            return "Good"
        elif overall_score >= 0.4:
            return "Fair"
        else:
            return "Poor"