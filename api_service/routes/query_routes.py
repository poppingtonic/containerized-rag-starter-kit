"""
Query Routes with advanced prompting strategies
"""
import json
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from models import ChunkResponse, EntityResponse, CommunityResponse
from services.qa_service import QAService
from services.query_service import QueryService
from services.memory_service import MemoryService
from services.graph_service import GraphService
from utils import Config

router = APIRouter()
qa_service = QAService()
query_service = QueryService()
memory_service = MemoryService()
graph_service = GraphService()

class Query(BaseModel):
    query: str
    max_results: int = 5
    use_memory: bool = True
    use_amplification: bool = True
    use_smart_selection: bool = True

class SubQuestionResponse(BaseModel):
    question: str
    answer: str

class FullResponse(BaseModel):
    query: str
    answer: str
    chunks: List[ChunkResponse]
    entities: List[EntityResponse]
    communities: List[CommunityResponse]
    references: List[str]
    subquestions: Optional[List[SubQuestionResponse]] = []
    verification_score: Optional[float] = None
    from_memory: bool = False
    memory_id: Optional[int] = None
    processing_time: Optional[float] = None

@router.post("/query", response_model=FullResponse)
async def process_query(query_data: Query):
    """
    Process a query using QA strategies including:
    - Smart chunk classification and selection
    - Subquestion decomposition for complex queries
    - Answer verification
    - Security-aware prompting
    """
    start_time = time.time()
    
    try:
        # Create query embedding
        query_embedding = query_service.create_embedding(query_data.query)
        
        # Check memory if enabled
        if Config.ENABLE_MEMORY and query_data.use_memory:
            memory_result = memory_service.check_memory(query_data.query, query_embedding)
            if memory_result:
                # Add processing time and return cached result
                memory_result["processing_time"] = time.time() - start_time
                return memory_result
        
        # Perform vector search to get initial chunks
        all_chunks = query_service.vector_search(query_embedding, query_data.max_results * 2)
        
        # Smart chunk selection using classification
        if query_data.use_smart_selection and len(all_chunks) > query_data.max_results:
            selected_chunks = await qa_service.smart_chunk_selection(
                all_chunks, query_data.query, query_data.max_results
            )
        else:
            selected_chunks = all_chunks[:query_data.max_results]
        
        # Load graph data and enhance results
        entities, communities = graph_service.enhance_with_graph(selected_chunks)
        
        # Generate  answer with optional amplification
        answer, subquestions_data, verification_score = await qa_service.answer_generation(
            query_data.query, 
            selected_chunks, 
            use_amplification=query_data.use_amplification
        )
        
        # Extract references from chunks
        references = []
        for chunk in selected_chunks:
            # Handle source_metadata (jsonb column returns dict, not string)
            if isinstance(chunk['source_metadata'], str):
                metadata = json.loads(chunk['source_metadata'])
            else:
                metadata = chunk['source_metadata']
            source = metadata.get('source', 'Unknown source')
            if source not in references:
                references.append(source)
        
        # Save to memory
        memory_id = memory_service.save_to_memory(
            query_data.query, 
            query_embedding, 
            answer, 
            references, 
            selected_chunks, 
            entities[:10] if entities else [], 
            communities[:5] if communities else []
        )
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Format response
        response = {
            "query": query_data.query,
            "answer": answer,
            "chunks": [
                {
                    "id": chunk["id"],
                    "text": chunk["text_content"],
                    "source": (json.loads(chunk["source_metadata"]) if isinstance(chunk["source_metadata"], str) 
                             else chunk["source_metadata"]).get("source", "Unknown source"),
                    "similarity": float(chunk["similarity"])
                } for chunk in selected_chunks
            ],
            "entities": entities[:10],
            "communities": communities[:5],
            "references": references,
            "subquestions": [
                {
                    "question": sq["question"],
                    "answer": sq["answer"]
                } for sq in subquestions_data
            ],
            "verification_score": verification_score,
            "from_memory": False,
            "memory_id": memory_id if memory_id is not None else -1,
            "processing_time": processing_time
        }
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")

@router.post("/query/classify-chunks")
async def classify_chunks(query: str, chunk_ids: List[int]):
    """
    Classify the relevance of specific chunks to a query.
    Useful for debugging and analysis.
    """
    try:
        from utils import get_db_connection
        
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Get chunks by IDs
                format_strings = ','.join(['%s'] * len(chunk_ids))
                cursor.execute(f"""
                    SELECT id, text_content, source_metadata
                    FROM document_chunks
                    WHERE id IN ({format_strings})
                """, chunk_ids)
                
                chunks = cursor.fetchall()
        
        # Classify each chunk
        classifications = []
        for chunk in chunks:
            relevance_score = await qa_service.classify_chunk_relevance(chunk, query)
            classifications.append({
                "chunk_id": chunk["id"],
                "relevance_score": relevance_score,
                "is_relevant": relevance_score > 0.5,
                "text_preview": chunk["text_content"][:200] + "..." if len(chunk["text_content"]) > 200 else chunk["text_content"]
            })
        
        return {
            "query": query,
            "classifications": classifications,
            "total_chunks": len(classifications),
            "relevant_chunks": sum(1 for c in classifications if c["is_relevant"])
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chunk classification failed: {str(e)}")

@router.post("/query/generate-subquestions")
async def generate_subquestions_endpoint(query: str, context: Optional[str] = None):
    """
    Generate subquestions for a given query and optional context.
    Useful for understanding how complex queries are decomposed.
    """
    try:
        if not context:
            # Get some context from top chunks
            query_embedding = query_service.create_embedding(query)
            chunks = query_service.vector_search(query_embedding, 3)
            context = "\n\n".join([chunk['text_content'] for chunk in chunks])
        
        subquestions = await qa_service.generate_subquestions(query, context)
        
        return {
            "query": query,
            "subquestions": subquestions,
            "context_length": len(context),
            "num_subquestions": len(subquestions)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Subquestion generation failed: {str(e)}")

@router.post("/query/verify-answer")
async def verify_answer_endpoint(query: str, answer: str, context: Optional[str] = None):
    """
    Verify if an answer is supported by the provided context.
    """
    try:
        if not context:
            # Get some context from top chunks
            query_embedding = query_service.create_embedding(query)
            chunks = query_service.vector_search(query_embedding, 5)
            context = "\n\n".join([chunk['text_content'] for chunk in chunks])
        
        verification_score = await qa_service.verify_answer(query, answer, context)
        
        return {
            "query": query,
            "answer": answer,
            "verification_score": verification_score,
            "is_supported": verification_score > 0.7,
            "context_length": len(context)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Answer verification failed: {str(e)}")