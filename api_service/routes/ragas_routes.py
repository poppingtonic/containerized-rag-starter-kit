from fastapi import APIRouter, HTTPException, Body
from typing import List, Optional
from pydantic import BaseModel
from utils import get_db_connection
import json

router = APIRouter()

class RagasEvaluationRequest(BaseModel):
    query: str
    answer: str
    contexts: List[str]
    ground_truth: Optional[str] = None

class BatchEvaluationRequest(BaseModel):
    memory_ids: List[int]
    include_ground_truth: bool = False

# Temporary mock implementations while RAGAS is disabled

@router.post("/evaluate")
async def evaluate_single_query(request: RagasEvaluationRequest):
    """
    Evaluate a single query-answer pair using RAGAS metrics.
    """
    # Temporarily return mock data
    return {
        "status": "success",
        "message": "RAGAS evaluation temporarily disabled due to version conflicts",
        "scores": {
            "faithfulness": 0.85,
            "answer_relevancy": 0.90,
            "context_precision": 0.88,
            "overall_score": 0.88
        }
    }

@router.post("/evaluate/batch")
async def evaluate_batch(request: BatchEvaluationRequest):
    """
    Evaluate multiple cached queries using RAGAS metrics.
    """
    # Temporarily return mock data
    return {
        "status": "success",
        "message": "RAGAS batch evaluation temporarily disabled",
        "results": {
            "faithfulness_avg": 0.85,
            "answer_relevancy_avg": 0.90,
            "context_precision_avg": 0.88,
            "overall_score_avg": 0.88
        }
    }

@router.get("/evaluate/{memory_id}")
async def evaluate_memory_entry(memory_id: int):
    """
    Evaluate a specific cached query using RAGAS metrics.
    """
    # Temporarily return mock data
    return {
        "status": "success",
        "message": "RAGAS evaluation temporarily disabled",
        "memory_id": memory_id,
        "scores": {
            "faithfulness": 0.85,
            "answer_relevancy": 0.90,
            "context_precision": 0.88,
            "overall_score": 0.88
        }
    }

@router.get("/metrics/explanations")
async def get_metric_explanations():
    """
    Get explanations for RAGAS metrics.
    """
    return {
        "metrics": {
            "faithfulness": {
                "name": "Faithfulness",
                "description": "Measures how factually accurate the generated answer is with respect to the given context",
                "range": "0-1 (higher is better)"
            },
            "answer_relevancy": {
                "name": "Answer Relevancy",
                "description": "Measures how relevant the answer is to the given question",
                "range": "0-1 (higher is better)"
            },
            "context_precision": {
                "name": "Context Precision",
                "description": "Measures whether all relevant items in the context are ranked higher",
                "range": "0-1 (higher is better)"
            },
            "context_recall": {
                "name": "Context Recall",
                "description": "Measures whether all ground-truth relevant items are present in the retrieved context",
                "range": "0-1 (higher is better)"
            },
            "overall_score": {
                "name": "Overall RAGAS Score",
                "description": "Harmonic mean of all individual metrics",
                "range": "0-1 (higher is better)"
            }
        }
    }