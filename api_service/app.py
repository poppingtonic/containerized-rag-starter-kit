import os
import json
import time
import pandas as pd
import networkx as nx
import jsonlines
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
from openai import OpenAI

# Configuration from environment variables
DB_URL = os.environ.get("DATABASE_URL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GRAPH_OUTPUT_PATH = os.environ.get("GRAPH_OUTPUT_PATH", "/app/graph_data")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize FastAPI app
app = FastAPI(title="GraphRAG API", 
              description="API for querying documents with GraphRAG-enhanced retrieval",
              version="1.0.0")

# Model definitions
class Query(BaseModel):
    query: str
    max_results: int = 5

class ChunkResponse(BaseModel):
    id: int
    text: str
    source: str
    similarity: float

class EntityResponse(BaseModel):
    entity: str
    entity_type: str
    relevance: float

class CommunityResponse(BaseModel):
    community_id: int
    summary: str
    entities: List[str]
    relevance: float

class FullResponse(BaseModel):
    query: str
    answer: str
    chunks: List[ChunkResponse]
    entities: List[EntityResponse]
    communities: List[CommunityResponse]
    references: List[str]

# Database connection
def get_db_connection():
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)

# Load GraphRAG outputs
def load_graph_data():
    try:
        # Load latest references
        refs_path = os.path.join(GRAPH_OUTPUT_PATH, "latest_refs.json")
        if not os.path.exists(refs_path):
            print("No GraphRAG data found. Using vector search only.")
            return None, None, None
            
        with open(refs_path, 'r') as f:
            refs = json.load(f)
        
        # Load edges
        edges_df = pd.read_csv(refs["edges"])
        
        # Load nodes
        nodes_df = pd.read_csv(refs["nodes"])
        
        # Load summaries
        summaries = []
        with jsonlines.open(refs["summaries"]) as reader:
            for summary in reader:
                summaries.append(summary)
        
        # Build graph
        G = nx.Graph()
        
        # Add nodes
        for _, row in nodes_df.iterrows():
            G.add_node(row["id"], 
                      type=row["type"], 
                      entity_type=row["entity_type"], 
                      text=row["text"],
                      source=row["source"])
        
        # Add edges
        for _, row in edges_df.iterrows():
            G.add_edge(row["source"], row["target"], weight=row["weight"])
        
        return G, summaries, refs
        
    except Exception as e:
        print(f"Error loading graph data: {e}")
        return None, None, None

# Create embeddings using OpenAI
def create_embedding(text):
    response = client.embeddings.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response.data[0].embedding

# Vector search
def vector_search(query_embedding, max_results=5):
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # Convert embedding list to a string representation for pgvector
            embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
            
            cursor.execute("""
                SELECT 
                    dc.id, 
                    dc.text_content, 
                    dc.source_metadata,
                    1 - (ce.embedding_vector <=> %s::vector) as similarity
                FROM 
                    chunk_embeddings ce
                JOIN 
                    document_chunks dc ON ce.chunk_id = dc.id
                ORDER BY 
                    ce.embedding_vector <=> %s::vector
                LIMIT %s
            """, (embedding_str, embedding_str, max_results))
            
            results = cursor.fetchall()
            return results

# Generate answer with references
def generate_answer(query, chunks, entities=None, communities=None):
    # Prepare context from chunks
    chunks_context = "\n\n".join([f"Document chunk {i+1}:\n{chunk['text_content']}" 
                                 for i, chunk in enumerate(chunks)])
    
    # Add entity information if available
    entities_context = ""
    if entities:
        entities_context = "\nRelevant entities:\n" + "\n".join([
            f"- {entity['entity']} ({entity['entity_type']}): {entity['relevance']:.2f} relevance" 
            for entity in entities
        ])
    
    # Add community summaries if available
    communities_context = ""
    if communities:
        communities_context = "\nCommunity insights:\n" + "\n".join([
            f"- Community {comm['community_id']}: {comm['summary']}" 
            for comm in communities
        ])
    
    # Full context for the model
    full_context = chunks_context + entities_context + communities_context
    
    # Create references for citation
    references = []
    for chunk in chunks:
        metadata = json.loads(chunk['source_metadata']) if isinstance(chunk['source_metadata'], str) else chunk['source_metadata']
        source = metadata.get('source', 'Unknown source')
        if source not in references:
            references.append(source)
    
    # Generate answer with OpenAI
    prompt = f"""
    Generate a comprehensive answer to the following query based on the provided context. 
    
    Query: {query}
    
    Context:
    {full_context}
    
    Guidelines:
    1. Answer the query using ONLY the information in the provided context.
    2. If the context doesn't contain enough information to fully answer the query, acknowledge the limitations.
    3. Include parenthetical citations when referring to specific information, using the format [doc1], [doc2], etc.
    4. Write in a clear, informative, and authoritative style.
    5. Make connections between different pieces of information where relevant.
    6. The answer should be 1-2 paragraphs (3-8 sentences).
    
    References to use (in order):
    {', '.join([f'[{i+1}] {ref}' for i, ref in enumerate(references)])}
    """
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a knowledgeable assistant that provides well-researched answers with proper citations."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        temperature=0.5
    )
    
    answer = response.choices[0].message.content.strip()
    return answer, references

# Routes
@app.get("/")
async def root():
    return {"message": "GraphRAG API is running. Use /query endpoint to search."}

@app.post("/query", response_model=FullResponse)
async def process_query(query_data: Query):
    # Create embedding for query
    query_embedding = create_embedding(query_data.query)
    
    # Vector search
    chunks = vector_search(query_embedding, query_data.max_results)
    
    # Load graph data
    G, summaries, refs = load_graph_data()
    
    entities = []
    communities = []
    
    # GraphRAG enhanced retrieval
    if G and summaries:
        # Find relevant entities based on retrieved chunks
        relevant_chunks = [f"chunk_{chunk['id']}" for chunk in chunks]
        relevant_entities = set()
        
        for chunk_id in relevant_chunks:
            if chunk_id in G:
                # Get connected entities
                for neighbor in G.neighbors(chunk_id):
                    if G.nodes[neighbor]["type"] == "entity":
                        relevant_entities.add(neighbor)
        
        # Score entities by connection to retrieved chunks
        entity_scores = {}
        for entity in relevant_entities:
            connections = sum(1 for chunk in relevant_chunks if G.has_edge(entity, chunk))
            relevance = connections / len(relevant_chunks)
            entity_scores[entity] = relevance
            
            entities.append({
                "entity": G.nodes[entity]["text"],
                "entity_type": G.nodes[entity]["entity_type"],
                "relevance": relevance
            })
        
        # Find relevant communities
        relevant_communities = set()
        for summary in summaries:
            # Check if any retrieved chunks are in this community
            if any(chunk_id in summary["related_chunks"] for chunk in chunks for chunk_id in [chunk["id"]]):
                relevant_communities.add(summary["community_id"])
            
            # Check if any relevant entities are mentioned in this community
            if any(entity_info in summary["entities"] for entity in relevant_entities 
                  for entity_info in summary["entities"] if G.nodes[entity]["text"] in entity_info):
                relevant_communities.add(summary["community_id"])
        
        # Add community information
        for summary in summaries:
            if summary["community_id"] in relevant_communities:
                # Calculate relevance based on chunk and entity overlap
                chunk_overlap = sum(1 for chunk in chunks if chunk["id"] in summary["related_chunks"])
                entity_overlap = sum(1 for entity in relevant_entities 
                                   for entity_info in summary["entities"] if G.nodes[entity]["text"] in entity_info)
                
                total_factors = len(chunks) + len(relevant_entities)
                if total_factors > 0:
                    relevance = (chunk_overlap + entity_overlap) / total_factors
                else:
                    relevance = 0.0
                
                communities.append({
                    "community_id": summary["community_id"],
                    "summary": summary["summary"],
                    "entities": summary["entities"],
                    "relevance": relevance
                })
    
    # Sort by relevance
    entities.sort(key=lambda x: x["relevance"], reverse=True)
    communities.sort(key=lambda x: x["relevance"], reverse=True)
    
    # Generate answer
    answer, references = generate_answer(
        query_data.query, 
        chunks, 
        entities[:5] if entities else None, 
        communities[:3] if communities else None
    )
    
    # Format response
    response = {
        "query": query_data.query,
        "answer": answer,
        "chunks": [
            {
                "id": chunk["id"],
                "text": chunk["text_content"],
                "source": json.loads(chunk["source_metadata"])["source"] if isinstance(chunk["source_metadata"], str) 
                         else chunk["source_metadata"]["source"],
                "similarity": float(chunk["similarity"])
            } for chunk in chunks
        ],
        "entities": entities[:10],  # Top 10 entities
        "communities": communities[:5],  # Top 5 communities
        "references": references
    }
    
    return response

# Health check endpoint
@app.get("/health")
async def health_check():
    try:
        # Check database connection
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        
        # Check graph data
        _, _, refs = load_graph_data()
        graph_status = "available" if refs else "unavailable"
        
        return {
            "status": "healthy",
            "database": "connected",
            "graph_data": graph_status
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@app.get("/ingestion/progress")
async def ingestion_progress():
    """Provide comprehensive statistics about document ingestion progress."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Get overall statistics
                cursor.execute("""
                    SELECT 
                        COUNT(*) AS total_chunks,
                        COUNT(DISTINCT source_metadata->>'source') AS unique_documents
                    FROM document_chunks
                """)
                overall_stats = cursor.fetchone()
                
                # Get embedding status
                cursor.execute("""
                    SELECT 
                        (SELECT COUNT(*) FROM document_chunks) AS total_chunks,
                        (SELECT COUNT(*) FROM chunk_embeddings) AS chunks_with_embeddings
                """)
                embedding_stats = cursor.fetchone()
                
                # Get OCR statistics
                cursor.execute("""
                    SELECT 
                        COUNT(DISTINCT source_metadata->>'source') AS documents_with_ocr
                    FROM document_chunks
                    WHERE source_metadata->>'ocr_applied' = 'true'
                """)
                ocr_stats = cursor.fetchone()
                
                # Get recent documents
                cursor.execute("""
                    SELECT 
                        source_metadata->>'source' AS document,
                        source_metadata->>'processed_at' AS processed_at,
                        source_metadata->>'ocr_applied' AS ocr_applied,
                        COUNT(*) AS chunk_count
                    FROM document_chunks
                    GROUP BY document, processed_at, ocr_applied
                    ORDER BY processed_at DESC NULLS LAST
                    LIMIT 10
                """)
                recent_documents = cursor.fetchall()
                
                # Get ingestion rate (per hour)
                cursor.execute("""
                    SELECT 
                        date_trunc('hour', created_at) AS hour,
                        COUNT(*) AS chunks_processed
                    FROM document_chunks
                    GROUP BY hour
                    ORDER BY hour DESC
                    LIMIT 24
                """)
                ingestion_rate = cursor.fetchall()
                
                # Get document types stats
                cursor.execute("""
                    SELECT 
                        source_metadata->>'extension' AS file_type,
                        COUNT(DISTINCT source_metadata->>'source') AS document_count
                    FROM document_chunks
                    GROUP BY file_type
                    ORDER BY document_count DESC
                """)
                document_types = cursor.fetchall()
                
                return {
                    "overall": {
                        "total_chunks": overall_stats["total_chunks"],
                        "unique_documents": overall_stats["unique_documents"],
                    },
                    "embeddings": {
                        "total_chunks": embedding_stats["total_chunks"],
                        "chunks_with_embeddings": embedding_stats["chunks_with_embeddings"],
                        "completion_percentage": round(
                            (embedding_stats["chunks_with_embeddings"] / embedding_stats["total_chunks"]) * 100 
                            if embedding_stats["total_chunks"] > 0 else 0, 
                            2
                        )
                    },
                    "ocr": {
                        "documents_with_ocr": ocr_stats["documents_with_ocr"]
                    },
                    "recent_documents": [dict(doc) for doc in recent_documents],
                    "ingestion_rate": [
                        {
                            "hour": rate["hour"].isoformat() if rate["hour"] else None,
                            "chunks_processed": rate["chunks_processed"]
                        } 
                        for rate in ingestion_rate
                    ],
                    "document_types": [dict(doc_type) for doc_type in document_types]
                }
    except Exception as e:
        return {
            "error": str(e)
        }

@app.post("/ingestion/trigger")
async def trigger_ingestion():
    """Trigger the ingestion service to reprocess documents."""
    import httpx
    
    try:
        # Call the ingestion service API directly
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://ingestion-service:5050/trigger-ingestion", 
                timeout=5.0
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "status": "success",
                    "message": "Ingestion service triggered successfully",
                    "details": result,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            else:
                return {
                    "status": "error",
                    "message": f"Ingestion service returned error code: {response.status_code}",
                    "details": response.text,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to trigger ingestion service: {str(e)}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }