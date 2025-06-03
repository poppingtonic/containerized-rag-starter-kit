import os
import json
import time
import pandas as pd
import networkx as nx
import jsonlines
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Query, Body
from pydantic import BaseModel, Field
import psycopg2
from psycopg2.extras import RealDictCursor
from openai import OpenAI
import numpy as np
from uuid import uuid4

# Configuration from environment variables
DB_URL = os.environ.get("DATABASE_URL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GRAPH_OUTPUT_PATH = os.environ.get("GRAPH_OUTPUT_PATH", "/app/graph_data")
ENABLE_MEMORY = os.environ.get("ENABLE_MEMORY", "true").lower() == "true"
MEMORY_SIMILARITY_THRESHOLD = float(os.environ.get("MEMORY_SIMILARITY_THRESHOLD", "0.95"))
ENABLE_DIALOG_RETRIEVAL = os.environ.get("ENABLE_DIALOG_RETRIEVAL", "true").lower() == "true"

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
    use_memory: bool = True

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
    from_memory: bool = False
    memory_id: Optional[int] = None

class FeedbackRequest(BaseModel):
    memory_id: int
    feedback_text: Optional[str] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    is_favorite: Optional[bool] = None

class ThreadCreateRequest(BaseModel):
    memory_id: int
    thread_title: str

class ThreadMessageRequest(BaseModel):
    feedback_id: int
    message: str
    enhance_with_retrieval: bool = False
    max_results: int = 3

class ThreadMessageResponse(BaseModel):
    id: int
    message: str
    is_user: bool
    references: List[str]
    chunks: Optional[List[ChunkResponse]] = None
    created_at: str

class ThreadResponse(BaseModel):
    id: int
    title: str
    memory_id: int
    original_query: str
    original_answer: str
    messages: List[ThreadMessageResponse]
    created_at: str

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
    4. Ensure the number of references in your response matches the number of references provided.
    5. Write in a clear, informative, and authoritative style.
    6. Make connections between different pieces of information where relevant.
    7. The answer should be 1-2 paragraphs (3-8 sentences).
    
    References to use (in order):
    {', '.join([f'[{i+1}] {ref}' for i, ref in enumerate(references)])}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a knowledgeable assistant that provides well-researched answers with proper citations."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        temperature=0.5
    )
    
    answer = response.choices[0].message.content.strip()
    return answer, references

# Generate thread message with optional retrieval enhancement
def generate_thread_message(message, previous_messages=None, retrieve_chunks=False, max_results=3):
    # If retrieval is enabled, get relevant chunks
    retrieved_chunks = []
    if retrieve_chunks and ENABLE_DIALOG_RETRIEVAL:
        # Create embedding for the message
        message_embedding = create_embedding(message)
        
        # Get relevant chunks
        retrieved_chunks = vector_search(message_embedding, max_results)
    
    # Prepare context
    chunks_context = ""
    if retrieved_chunks:
        chunks_context = "Relevant document excerpts:\n" + "\n\n".join([
            f"Document chunk {i+1}:\n{chunk['text_content']}" 
            for i, chunk in enumerate(retrieved_chunks)
        ])
    
    # Create references for citation
    references = []
    for chunk in retrieved_chunks:
        metadata = json.loads(chunk['source_metadata']) if isinstance(chunk['source_metadata'], str) else chunk['source_metadata']
        source = metadata.get('source', 'Unknown source')
        if source not in references:
            references.append(source)
    
    # Prepare conversation history context
    conversation_context = ""
    if previous_messages:
        formatted_messages = []
        for msg in previous_messages:
            role = "User" if msg['is_user'] else "Assistant"
            formatted_messages.append(f"{role}: {msg['message_text']}")
        
        conversation_context = "Previous conversation:\n" + "\n".join(formatted_messages)
    
    # Full context for the model
    full_context = []
    if conversation_context:
        full_context.append(conversation_context)
    if chunks_context:
        full_context.append(chunks_context)
    
    full_context_str = "\n\n".join(full_context)
    
    # Generate answer with OpenAI
    prompt = f"""
    The user has sent you the following message in an ongoing conversation. 
    Respond to their message in a helpful and informative way.
    
    User message: {message}
    
    {full_context_str}
    
    Guidelines:
    1. If document excerpts are provided, incorporate that information into your response.
    2. Include parenthetical citations when referring to specific information from documents, using the format [doc1], [doc2], etc.
    3. Focus on answering the specific question or addressing the current message.
    4. Be conversational and engaging while remaining informative.
    5. If the context doesn't contain enough information, be honest about limitations.
    
    References to use (in order):
    {', '.join([f'[{i+1}] {ref}' for i, ref in enumerate(references)])}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a knowledgeable assistant that provides well-researched answers with proper citations."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        temperature=0.7
    )
    
    answer = response.choices[0].message.content.strip()
    return answer, references, retrieved_chunks

# Check memory for similar query and return remembered result if found
def check_memory(query, query_embedding):
    if not ENABLE_MEMORY:
        return None
        
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # First try exact match
                cursor.execute("""
                    SELECT * FROM query_cache 
                    WHERE LOWER(query_text) = LOWER(%s)
                    ORDER BY created_at DESC LIMIT 1
                """, (query,))
                
                result = cursor.fetchone()
                if result:
                    # Update last accessed timestamp
                    cursor.execute("""
                        UPDATE query_cache 
                        SET last_accessed = CURRENT_TIMESTAMP 
                        WHERE id = %s
                    """, (result['id'],))
                    conn.commit()
                    return result
                
                # Then try vector similarity
                embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
                cursor.execute("""
                    SELECT *, 1 - (query_embedding <=> %s::vector) as similarity 
                    FROM query_cache 
                    WHERE query_embedding IS NOT NULL
                    ORDER BY query_embedding <=> %s::vector
                    LIMIT 1
                """, (embedding_str, embedding_str))
                
                result = cursor.fetchone()
                if result and result['similarity'] >= MEMORY_SIMILARITY_THRESHOLD:
                    # Update last accessed timestamp
                    cursor.execute("""
                        UPDATE query_cache 
                        SET last_accessed = CURRENT_TIMESTAMP 
                        WHERE id = %s
                    """, (result['id'],))
                    conn.commit()
                    return result
                
        return None
    except Exception as e:
        print(f"Error checking memory: {e}")
        return None

# Save result to memory
def save_to_memory(query, query_embedding, answer, references, chunks, entities, communities):
    if not ENABLE_MEMORY:
        return None
        
    try:
        # Prepare chunk IDs
        chunk_ids = [chunk['id'] for chunk in chunks]
        
        # Format entities and communities for storage
        formatted_entities = []
        for entity in entities:
            formatted_entities.append({
                "entity": entity["entity"],
                "entity_type": entity["entity_type"],
                "relevance": float(entity["relevance"])
            })
            
        formatted_communities = []
        for community in communities:
            formatted_communities.append({
                "community_id": community["community_id"],
                "summary": community["summary"],
                "entities": community["entities"],
                "relevance": float(community["relevance"])
            })
            
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Convert embedding to string for storage
                embedding_str = '[' + ','.join(map(str, query_embedding)) + ']' if query_embedding else None
                
                # Serialize JSON fields
                chunk_ids_json = json.dumps(chunk_ids)
                references_json = json.dumps(references)
                entities_json = json.dumps(formatted_entities)
                communities_json = json.dumps(formatted_communities)
                
                # Insert into memory
                cursor.execute("""
                    INSERT INTO query_cache 
                    (query_text, query_embedding, answer_text, references, chunk_ids, entities, communities) 
                    VALUES (%s, %s::vector, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    query, 
                    embedding_str, 
                    answer, 
                    references_json, 
                    chunk_ids_json, 
                    entities_json, 
                    communities_json
                ))
                
                inserted_id = cursor.fetchone()['id']
                conn.commit()
                return inserted_id
    except Exception as e:
        print(f"Error saving to memory: {e}")
        return None

# Routes
@app.get("/")
async def root():
    return {"message": "GraphRAG API is running. Use /query endpoint to search."}

@app.post("/query", response_model=FullResponse)
async def process_query(query_data: Query):
    # Create embedding for query
    query_embedding = create_embedding(query_data.query)
    
    # Check memory if enabled
    memory_id = None
    if query_data.use_memory:
        memory_result = check_memory(query_data.query, query_embedding)
        if memory_result:
            print(f"Memory recall for query: {query_data.query}")
            memory_id = memory_result['id']
            
            # Rebuild response from memory
            return {
                "query": query_data.query,
                "answer": memory_result['answer_text'],
                "chunks": [
                    # Fetch chunks from database using remembered IDs
                    await fetch_chunk_by_id(chunk_id) 
                    for chunk_id in json.loads(memory_result['chunk_ids'])
                ],
                "entities": json.loads(memory_result['entities']),
                "communities": json.loads(memory_result['communities']),
                "references": json.loads(memory_result['references']),
                "from_memory": True,
                "memory_id": memory_id
            }
    
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
    
    # Save to memory
    memory_id = save_to_memory(
        query_data.query, 
        query_embedding, 
        answer, 
        references, 
        chunks, 
        entities[:10] if entities else [], 
        communities[:5] if communities else []
    )
    
    # Ensure memory_id is never None
    if memory_id is None and ENABLE_MEMORY:
        print("Warning: Failed to save to memory, retrying...")
        # Retry once
        memory_id = save_to_memory(
            query_data.query, 
            query_embedding, 
            answer, 
            references, 
            chunks, 
            entities[:10] if entities else [], 
            communities[:5] if communities else []
        )
    
    # Ensure we have a valid memory_id, use -1 as fallback
    memory_id = memory_id if memory_id is not None else -1
    
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
        "references": references,
        "from_memory": False,
        "memory_id": memory_id
    }
    
    return response

# Helper function to fetch a single chunk by ID
async def fetch_chunk_by_id(chunk_id):
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    dc.id, 
                    dc.text_content, 
                    dc.source_metadata
                FROM 
                    document_chunks dc
                WHERE 
                    dc.id = %s
            """, (chunk_id,))
            
            chunk = cursor.fetchone()
            if chunk:
                return {
                    "id": chunk["id"],
                    "text": chunk["text_content"],
                    "source": json.loads(chunk["source_metadata"])["source"] if isinstance(chunk["source_metadata"], str) 
                             else chunk["source_metadata"]["source"],
                    "similarity": 1.0  # Set to 1.0 for remembered results
                }
            else:
                # Return placeholder if chunk not found
                return {
                    "id": chunk_id,
                    "text": "Chunk not found",
                    "source": "Unknown source",
                    "similarity": 0.0
                }

# Feedback routes
@app.post("/feedback")
async def save_feedback(feedback: FeedbackRequest):
    """Save user feedback for a query"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Check if memory ID exists
                cursor.execute("SELECT id FROM query_cache WHERE id = %s", (feedback.memory_id,))
                if not cursor.fetchone():
                    return {
                        "status": "error",
                        "message": f"Memory entry with ID {feedback.memory_id} not found"
                    }
                
                # Check if feedback already exists
                cursor.execute("SELECT id FROM user_feedback WHERE query_cache_id = %s", (feedback.memory_id,))
                existing_feedback = cursor.fetchone()
                
                if existing_feedback:
                    # Update existing feedback
                    update_parts = []
                    update_values = []
                    
                    if feedback.feedback_text is not None:
                        update_parts.append("feedback_text = %s")
                        update_values.append(feedback.feedback_text)
                        
                    if feedback.rating is not None:
                        update_parts.append("rating = %s")
                        update_values.append(feedback.rating)
                        
                    if feedback.is_favorite is not None:
                        update_parts.append("is_favorite = %s")
                        update_values.append(feedback.is_favorite)
                    
                    update_parts.append("updated_at = CURRENT_TIMESTAMP")
                    
                    if update_parts:
                        query = f"""
                            UPDATE user_feedback 
                            SET {", ".join(update_parts)}
                            WHERE id = %s
                            RETURNING id
                        """
                        update_values.append(existing_feedback['id'])
                        cursor.execute(query, update_values)
                        updated_id = cursor.fetchone()['id']
                        conn.commit()
                        
                        return {
                            "status": "success",
                            "message": "Feedback updated successfully",
                            "id": updated_id
                        }
                else:
                    # Create new feedback
                    cursor.execute("""
                        INSERT INTO user_feedback 
                        (query_cache_id, feedback_text, rating, is_favorite)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id
                    """, (
                        feedback.memory_id,
                        feedback.feedback_text,
                        feedback.rating,
                        feedback.is_favorite if feedback.is_favorite is not None else False
                    ))
                    
                    new_id = cursor.fetchone()['id']
                    conn.commit()
                    
                    return {
                        "status": "success",
                        "message": "Feedback saved successfully",
                        "id": new_id
                    }
                
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to save feedback: {str(e)}"
        }

@app.get("/favorites")
async def get_favorites():
    """Get all favorite queries"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        uf.id, 
                        uf.query_cache_id,
                        uf.feedback_text,
                        uf.rating, 
                        uf.created_at,
                        qc.query_text,
                        qc.answer_text
                    FROM 
                        user_feedback uf
                    JOIN 
                        query_cache qc ON uf.query_cache_id = qc.id
                    WHERE 
                        uf.is_favorite = TRUE
                    ORDER BY 
                        uf.created_at DESC
                """)
                
                favorites = cursor.fetchall()
                return [dict(favorite) for favorite in favorites]
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to retrieve favorites: {str(e)}"
        }

# Thread routes
@app.post("/thread/create")
async def create_thread(thread_request: ThreadCreateRequest):
    """Create a new discussion thread from a query"""
    try:
        # Validate memory ID
        if thread_request.memory_id <= 0:
            return {
                "status": "error",
                "message": f"Invalid memory ID: {thread_request.memory_id}"
            }
            
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Check if memory ID exists
                cursor.execute("""
                    SELECT id, query_text, answer_text 
                    FROM query_cache 
                    WHERE id = %s
                """, (thread_request.memory_id,))
                
                memory_entry = cursor.fetchone()
                if not memory_entry:
                    return {
                        "status": "error",
                        "message": f"Memory entry with ID {thread_request.memory_id} not found"
                    }
                
                # Check if a thread already exists for this memory ID
                cursor.execute("""
                    SELECT id FROM user_feedback 
                    WHERE query_cache_id = %s AND has_thread = TRUE
                """, (thread_request.memory_id,))
                
                existing_thread = cursor.fetchone()
                if existing_thread:
                    return {
                        "status": "error",
                        "message": f"A thread already exists for this query",
                        "thread_id": existing_thread['id']
                    }
                
                # Create new thread entry
                cursor.execute("""
                    INSERT INTO user_feedback 
                    (query_cache_id, thread_title, has_thread, is_favorite)
                    VALUES (%s, %s, TRUE, TRUE)
                    RETURNING id
                """, (
                    thread_request.memory_id,
                    thread_request.thread_title
                ))
                
                thread_id = cursor.fetchone()['id']
                
                # Add initial messages to the thread (the original query and answer)
                cursor.execute("""
                    INSERT INTO thread_messages
                    (feedback_id, message_text, is_user, references, chunk_ids)
                    VALUES
                    (%s, %s, TRUE, '[]', '[]')
                """, (
                    thread_id,
                    memory_entry['query_text']
                ))
                
                # Get references and chunk IDs from memory
                cursor.execute("""
                    SELECT references, chunk_ids 
                    FROM query_cache 
                    WHERE id = %s
                """, (thread_request.memory_id,))
                
                cache_data = cursor.fetchone()
                
                cursor.execute("""
                    INSERT INTO thread_messages
                    (feedback_id, message_text, is_user, references, chunk_ids)
                    VALUES
                    (%s, %s, FALSE, %s, %s)
                """, (
                    thread_id,
                    memory_entry['answer_text'],
                    cache_data['references'],
                    cache_data['chunk_ids']
                ))
                
                conn.commit()
                
                # Return success response with thread ID
                return {
                    "status": "success",
                    "message": "Thread created successfully",
                    "thread_id": thread_id
                }
                
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to create thread: {str(e)}"
        }

@app.get("/threads")
async def get_threads():
    """Get all discussion threads"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        uf.id, 
                        uf.thread_title,
                        uf.query_cache_id,
                        uf.created_at,
                        qc.query_text,
                        (
                            SELECT COUNT(*) 
                            FROM thread_messages 
                            WHERE feedback_id = uf.id
                        ) as message_count
                    FROM 
                        user_feedback uf
                    JOIN 
                        query_cache qc ON uf.query_cache_id = qc.id
                    WHERE 
                        uf.has_thread = TRUE
                    ORDER BY 
                        uf.created_at DESC
                """)
                
                threads = cursor.fetchall()
                return [dict(thread) for thread in threads]
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to retrieve threads: {str(e)}"
        }

@app.get("/thread/{thread_id}", response_model=ThreadResponse)
async def get_thread(thread_id: int):
    """Get a specific discussion thread with all messages"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Get thread data
                cursor.execute("""
                    SELECT 
                        uf.id, 
                        uf.thread_title,
                        uf.query_cache_id,
                        uf.created_at,
                        qc.query_text,
                        qc.answer_text
                    FROM 
                        user_feedback uf
                    JOIN 
                        query_cache qc ON uf.query_cache_id = qc.id
                    WHERE 
                        uf.id = %s AND uf.has_thread = TRUE
                """, (thread_id,))
                
                thread = cursor.fetchone()
                if not thread:
                    raise HTTPException(status_code=404, detail=f"Thread with ID {thread_id} not found")
                
                # Get thread messages
                cursor.execute("""
                    SELECT 
                        id, 
                        message_text, 
                        is_user, 
                        references,
                        chunk_ids,
                        created_at
                    FROM 
                        thread_messages
                    WHERE 
                        feedback_id = %s
                    ORDER BY 
                        created_at ASC
                """, (thread_id,))
                
                messages = cursor.fetchall()
                
                # Format the messages
                formatted_messages = []
                for msg in messages:
                    msg_dict = dict(msg)
                    
                    # Get chunks if needed
                    chunk_ids = json.loads(msg_dict['chunk_ids'])
                    chunks = None
                    if chunk_ids and not msg_dict['is_user']:
                        chunks = [
                            await fetch_chunk_by_id(chunk_id)
                            for chunk_id in chunk_ids
                        ]
                    
                    formatted_messages.append({
                        "id": msg_dict['id'],
                        "message": msg_dict['message_text'],
                        "is_user": msg_dict['is_user'],
                        "references": json.loads(msg_dict['references']),
                        "chunks": chunks,
                        "created_at": msg_dict['created_at'].isoformat() if msg_dict['created_at'] else None
                    })
                
                # Format the thread response
                thread_dict = dict(thread)
                return {
                    "id": thread_dict['id'],
                    "title": thread_dict['thread_title'],
                    "memory_id": thread_dict['query_cache_id'],
                    "original_query": thread_dict['query_text'],
                    "original_answer": thread_dict['answer_text'],
                    "messages": formatted_messages,
                    "created_at": thread_dict['created_at'].isoformat() if thread_dict['created_at'] else None
                }
                
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve thread: {str(e)}")

@app.post("/thread/message")
async def add_thread_message(message_request: ThreadMessageRequest):
    """Add a message to a discussion thread"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Check if thread exists
                cursor.execute("""
                    SELECT id FROM user_feedback 
                    WHERE id = %s AND has_thread = TRUE
                """, (message_request.feedback_id,))
                
                thread = cursor.fetchone()
                if not thread:
                    return {
                        "status": "error",
                        "message": f"Thread with ID {message_request.feedback_id} not found"
                    }
                
                # Get previous messages for context
                cursor.execute("""
                    SELECT message_text, is_user
                    FROM thread_messages
                    WHERE feedback_id = %s
                    ORDER BY created_at ASC
                """, (message_request.feedback_id,))
                
                previous_messages = cursor.fetchall()
                
                # Add the user message
                cursor.execute("""
                    INSERT INTO thread_messages
                    (feedback_id, message_text, is_user, references, chunk_ids)
                    VALUES
                    (%s, %s, TRUE, '[]', '[]')
                    RETURNING id
                """, (
                    message_request.feedback_id,
                    message_request.message
                ))
                
                user_message_id = cursor.fetchone()['id']
                
                # Generate assistant response
                assistant_response, references, retrieved_chunks = generate_thread_message(
                    message_request.message,
                    previous_messages,
                    message_request.enhance_with_retrieval,
                    message_request.max_results
                )
                
                # Prepare chunk IDs
                chunk_ids = [chunk['id'] for chunk in retrieved_chunks]
                
                # Add the assistant response
                cursor.execute("""
                    INSERT INTO thread_messages
                    (feedback_id, message_text, is_user, references, chunk_ids)
                    VALUES
                    (%s, %s, FALSE, %s, %s)
                    RETURNING id
                """, (
                    message_request.feedback_id,
                    assistant_response,
                    json.dumps(references),
                    json.dumps(chunk_ids)
                ))
                
                assistant_message_id = cursor.fetchone()['id']
                
                conn.commit()
                
                # Format chunks for response
                formatted_chunks = [
                    {
                        "id": chunk["id"],
                        "text": chunk["text_content"],
                        "source": json.loads(chunk["source_metadata"])["source"] if isinstance(chunk["source_metadata"], str) 
                                else chunk["source_metadata"]["source"],
                        "similarity": float(chunk["similarity"])
                    } for chunk in retrieved_chunks
                ]
                
                # Return the new messages
                return {
                    "status": "success",
                    "user_message": {
                        "id": user_message_id,
                        "message": message_request.message,
                        "is_user": True,
                        "references": []
                    },
                    "assistant_message": {
                        "id": assistant_message_id,
                        "message": assistant_response,
                        "is_user": False,
                        "references": references,
                        "chunks": formatted_chunks if formatted_chunks else None
                    }
                }
                
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to add message: {str(e)}"
        }

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
        
        # Check memory table
        memory_status = "unknown"
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM query_cache")
                    memory_count = cursor.fetchone()[0]
                    memory_status = f"available ({memory_count} entries)"
        except:
            memory_status = "table not found"
        
        # Check feedback tables
        feedback_status = "unknown"
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM user_feedback")
                    feedback_count = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT COUNT(*) FROM thread_messages")
                    thread_count = cursor.fetchone()[0]
                    
                    feedback_status = f"available ({feedback_count} feedback entries, {thread_count} thread messages)"
        except:
            feedback_status = "tables not found"
            
        return {
            "status": "healthy",
            "database": "connected",
            "graph_data": graph_status,
            "memory": memory_status,
            "feedback": feedback_status,
            "memory_enabled": ENABLE_MEMORY,
            "dialog_retrieval_enabled": ENABLE_DIALOG_RETRIEVAL
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

# Memory management endpoints
@app.get("/memory/stats")
async def memory_stats():
    """Get statistics about the system's memory of past queries."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Check if memory table exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'query_cache'
                    )
                """)
                
                table_exists = cursor.fetchone()[0]
                if not table_exists:
                    return {
                        "status": "unavailable",
                        "message": "Query memory table does not exist"
                    }
                
                # Get basic stats
                cursor.execute("SELECT COUNT(*) FROM query_cache")
                total_entries = cursor.fetchone()[0]
                
                # Get memory hit stats (if available)
                memory_recalls = {"total": "N/A", "percentage": "N/A"}
                
                # Get feedback stats
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_feedback,
                        COUNT(*) FILTER (WHERE is_favorite = TRUE) as favorites,
                        COUNT(*) FILTER (WHERE has_thread = TRUE) as threads
                    FROM user_feedback
                """)
                feedback_stats = cursor.fetchone()
                
                # Get recent queries
                cursor.execute("""
                    SELECT 
                        qc.id, 
                        qc.query_text, 
                        qc.created_at, 
                        qc.last_accessed,
                        array_length(qc.chunk_ids::json, 1) as chunk_count,
                        uf.is_favorite,
                        uf.has_thread
                    FROM query_cache qc
                    LEFT JOIN user_feedback uf ON qc.id = uf.query_cache_id
                    ORDER BY qc.last_accessed DESC
                    LIMIT 10
                """)
                recent_queries = cursor.fetchall()
                
                # Get time distribution
                cursor.execute("""
                    SELECT 
                        date_trunc('day', created_at) as day,
                        COUNT(*) as count
                    FROM query_cache
                    GROUP BY day
                    ORDER BY day DESC
                    LIMIT 7
                """)
                time_distribution = cursor.fetchall()
                
                return {
                    "status": "available",
                    "enabled": ENABLE_MEMORY,
                    "similarity_threshold": MEMORY_SIMILARITY_THRESHOLD,
                    "total_memories": total_entries,
                    "memory_recalls": memory_recalls,
                    "feedback": {
                        "total": feedback_stats["total_feedback"] if feedback_stats else 0,
                        "favorites": feedback_stats["favorites"] if feedback_stats else 0,
                        "threads": feedback_stats["threads"] if feedback_stats else 0
                    },
                    "recent_queries": [dict(q) for q in recent_queries],
                    "time_distribution": [
                        {
                            "day": day["day"].isoformat() if day["day"] else None,
                            "count": day["count"]
                        }
                        for day in time_distribution
                    ]
                }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@app.delete("/memory/clear")
async def clear_memory():
    """Clear all remembered queries."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("TRUNCATE TABLE query_cache CASCADE")
                conn.commit()
                
                return {
                    "status": "success",
                    "message": "Memory cleared successfully",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to clear memory: {str(e)}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

@app.get("/memory/entry/{entry_id}")
async def get_memory_entry(entry_id: int):
    """Get details about a specific remembered query."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT qc.*, uf.is_favorite, uf.has_thread, uf.id as feedback_id
                    FROM query_cache qc
                    LEFT JOIN user_feedback uf ON qc.id = uf.query_cache_id
                    WHERE qc.id = %s
                """, (entry_id,))
                
                entry = cursor.fetchone()
                
                if not entry:
                    return {
                        "status": "error",
                        "message": f"Memory entry with ID {entry_id} not found"
                    }
                
                # Format response
                entry_dict = dict(entry)
                return {
                    "id": entry_dict['id'],
                    "query": entry_dict['query_text'],
                    "answer": entry_dict['answer_text'],
                    "created_at": entry_dict['created_at'].isoformat() if entry_dict['created_at'] else None,
                    "last_accessed": entry_dict['last_accessed'].isoformat() if entry_dict['last_accessed'] else None,
                    "references": json.loads(entry_dict['references']),
                    "chunk_count": len(json.loads(entry_dict['chunk_ids'])),
                    "entity_count": len(json.loads(entry_dict['entities'])),
                    "community_count": len(json.loads(entry_dict['communities'])),
                    "is_favorite": entry_dict['is_favorite'] if entry_dict['is_favorite'] is not None else False,
                    "has_thread": entry_dict['has_thread'] if entry_dict['has_thread'] is not None else False,
                    "feedback_id": entry_dict['feedback_id']
                }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@app.delete("/memory/entry/{entry_id}")
async def delete_memory_entry(entry_id: int):
    """Delete a specific remembered query."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM query_cache WHERE id = %s RETURNING id", (entry_id,))
                deleted = cursor.fetchone()
                conn.commit()
                
                if not deleted:
                    return {
                        "status": "error",
                        "message": f"Memory entry with ID {entry_id} not found"
                    }
                
                return {
                    "status": "success",
                    "message": f"Memory entry with ID {entry_id} forgotten successfully",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }