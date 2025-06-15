"""
Legacy Query Routes - Simple querying without advanced features
"""
import json
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from models import ChunkResponse, EntityResponse, CommunityResponse
from services.query_service import QueryService
from services.memory_service import MemoryService
from services.graph_service import GraphService
from utils import Config

router = APIRouter()
query_service = QueryService()
memory_service = MemoryService()
graph_service = GraphService()

class LegacyQuery(BaseModel):
    query: str
    max_results: int = 5
    use_memory: bool = True

class LegacyResponse(BaseModel):
    query: str
    answer: str
    chunks: List[ChunkResponse]
    entities: List[EntityResponse]
    communities: List[CommunityResponse]
    references: List[str]
    from_memory: bool = False
    memory_id: Optional[int] = None
    processing_time: Optional[float] = None

@router.post("/query/simple", response_model=LegacyResponse)
async def process_simple_query(query_data: LegacyQuery):
    """
    Process a query using simple vector search without advanced QA features.
    This is the legacy endpoint for basic functionality.
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
        
        # Perform simple vector search
        chunks = query_service.vector_search(query_embedding, query_data.max_results)
        
        # Load graph data and enhance results
        entities, communities = graph_service.enhance_with_graph(chunks)
        
        # Generate simple answer using basic prompting
        context = "\n\n".join([chunk['text_content'] for chunk in chunks])
        answer = query_service.generate_simple_answer(query_data.query, context)
        
        # Extract references from chunks
        references = []
        for chunk in chunks:
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
            chunks, 
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
                } for chunk in chunks
            ],
            "entities": entities[:10],
            "communities": communities[:5],
            "references": references,
            "from_memory": False,
            "memory_id": memory_id if memory_id is not None else -1,
            "processing_time": processing_time
        }
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simple query processing failed: {str(e)}")