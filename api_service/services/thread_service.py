import json
from typing import List, Dict, Any, Optional
from openai import OpenAI
from models import ThreadCreateRequest, ThreadMessageRequest, ThreadMessageResponse, ThreadResponse
from utils import get_db_connection, Config
from .query_service import QueryService

class ThreadService:
    def __init__(self):
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.query_service = QueryService()
    
    def create_thread(self, request: ThreadCreateRequest) -> Dict[str, Any]:
        """Create a new conversation thread."""
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Get the original query and answer
                cursor.execute("""
                    SELECT query, answer FROM query_cache WHERE id = %s
                """, (request.memory_id,))
                
                cache_entry = cursor.fetchone()
                if not cache_entry:
                    return {
                        "status": "error",
                        "message": f"Memory entry with ID {request.memory_id} not found"
                    }
                
                # Check if feedback entry exists
                cursor.execute("""
                    SELECT id FROM user_feedback WHERE query_cache_id = %s
                """, (request.memory_id,))
                
                feedback_entry = cursor.fetchone()
                if feedback_entry:
                    # Update existing feedback to mark as thread
                    cursor.execute("""
                        UPDATE user_feedback 
                        SET is_thread = true, thread_title = %s
                        WHERE id = %s
                        RETURNING id
                    """, (request.thread_title, feedback_entry['id']))
                else:
                    # Create new feedback entry with thread
                    cursor.execute("""
                        INSERT INTO user_feedback 
                        (query_cache_id, is_thread, thread_title)
                        VALUES (%s, true, %s)
                        RETURNING id
                    """, (request.memory_id, request.thread_title))
                
                feedback_id = cursor.fetchone()['id']
                conn.commit()
                
                return {
                    "status": "success",
                    "message": "Thread created successfully",
                    "thread_id": feedback_id,
                    "memory_id": request.memory_id,
                    "title": request.thread_title
                }
    
    def get_all_threads(self) -> List[Dict[str, Any]]:
        """Get all conversation threads."""
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        uf.id,
                        uf.thread_title,
                        uf.query_cache_id,
                        uf.created_at,
                        qc.query,
                        COUNT(tm.id) as message_count
                    FROM user_feedback uf
                    INNER JOIN query_cache qc ON uf.query_cache_id = qc.id
                    LEFT JOIN thread_messages tm ON uf.id = tm.feedback_id
                    WHERE uf.is_thread = true
                    GROUP BY uf.id, uf.thread_title, uf.query_cache_id, uf.created_at, qc.query
                    ORDER BY uf.created_at DESC
                """)
                
                threads = cursor.fetchall()
                
                return [
                    {
                        "id": thread["id"],
                        "title": thread["thread_title"],
                        "memory_id": thread["query_cache_id"],
                        "original_query": thread["query"],
                        "message_count": thread["message_count"],
                        "created_at": thread["created_at"].isoformat() if thread["created_at"] else None
                    }
                    for thread in threads
                ]
    
    def get_thread(self, thread_id: int) -> Optional[ThreadResponse]:
        """Get a specific thread with all messages."""
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Get thread info
                cursor.execute("""
                    SELECT 
                        uf.id,
                        uf.thread_title,
                        uf.query_cache_id,
                        uf.created_at,
                        qc.query,
                        qc.answer
                    FROM user_feedback uf
                    INNER JOIN query_cache qc ON uf.query_cache_id = qc.id
                    WHERE uf.id = %s AND uf.is_thread = true
                """, (thread_id,))
                
                thread_info = cursor.fetchone()
                if not thread_info:
                    return None
                
                # Get messages
                cursor.execute("""
                    SELECT 
                        id,
                        message,
                        is_user,
                        references,
                        chunks,
                        created_at
                    FROM thread_messages
                    WHERE feedback_id = %s
                    ORDER BY created_at ASC
                """, (thread_id,))
                
                messages = cursor.fetchall()
                
                # Format messages
                formatted_messages = []
                for msg in messages:
                    formatted_msg = ThreadMessageResponse(
                        id=msg["id"],
                        message=msg["message"],
                        is_user=msg["is_user"],
                        references=json.loads(msg["references"]) if msg["references"] else [],
                        chunks=json.loads(msg["chunks"]) if msg["chunks"] else None,
                        created_at=msg["created_at"].isoformat() if msg["created_at"] else None
                    )
                    formatted_messages.append(formatted_msg)
                
                return ThreadResponse(
                    id=thread_info["id"],
                    title=thread_info["thread_title"],
                    memory_id=thread_info["query_cache_id"],
                    original_query=thread_info["query"],
                    original_answer=thread_info["answer"],
                    messages=formatted_messages,
                    created_at=thread_info["created_at"].isoformat() if thread_info["created_at"] else None
                )
    
    def add_message(self, request: ThreadMessageRequest) -> Dict[str, Any]:
        """Add a new message to a thread."""
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Verify thread exists
                cursor.execute("""
                    SELECT id FROM user_feedback 
                    WHERE id = %s AND is_thread = true
                """, (request.feedback_id,))
                
                if not cursor.fetchone():
                    return {
                        "status": "error",
                        "message": f"Thread with ID {request.feedback_id} not found"
                    }
                
                # Save user message
                cursor.execute("""
                    INSERT INTO thread_messages 
                    (feedback_id, message, is_user, references, chunks)
                    VALUES (%s, %s, true, NULL, NULL)
                    RETURNING id
                """, (request.feedback_id, request.message))
                
                user_message_id = cursor.fetchone()['id']
                
                # Get previous messages for context
                cursor.execute("""
                    SELECT message, is_user FROM thread_messages
                    WHERE feedback_id = %s
                    ORDER BY created_at ASC
                """, (request.feedback_id,))
                
                previous_messages = cursor.fetchall()
                
                # Generate response
                response_data = self._generate_thread_response(
                    request.message,
                    previous_messages[:-1],  # Exclude the just-added user message
                    request.enhance_with_retrieval,
                    request.max_results
                )
                
                # Save assistant response
                cursor.execute("""
                    INSERT INTO thread_messages 
                    (feedback_id, message, is_user, references, chunks)
                    VALUES (%s, %s, false, %s, %s)
                    RETURNING id
                """, (
                    request.feedback_id,
                    response_data["response"],
                    json.dumps(response_data["references"]),
                    json.dumps(response_data["chunks"]) if response_data.get("chunks") else None
                ))
                
                assistant_message_id = cursor.fetchone()['id']
                conn.commit()
                
                return {
                    "status": "success",
                    "user_message_id": user_message_id,
                    "assistant_message_id": assistant_message_id,
                    "response": response_data["response"],
                    "references": response_data["references"],
                    "chunks": response_data.get("chunks")
                }
    
    def _generate_thread_response(self, message: str, previous_messages: List[Dict], 
                                 enhance_with_retrieval: bool, max_results: int) -> Dict[str, Any]:
        """Generate a response for a thread message."""
        # Build conversation history
        messages = [{"role": "system", "content": "You are a knowledgeable assistant continuing a conversation about documents. Provide helpful, accurate responses based on the conversation context."}]
        
        for prev_msg in previous_messages:
            role = "user" if prev_msg["is_user"] else "assistant"
            messages.append({"role": role, "content": prev_msg["message"]})
        
        # Enhance with retrieval if requested
        chunks = None
        references = []
        
        if enhance_with_retrieval and Config.ENABLE_DIALOG_RETRIEVAL:
            # Perform vector search
            query_embedding = self.query_service.create_embedding(message)
            retrieved_chunks = self.query_service.vector_search(query_embedding, max_results)
            
            if retrieved_chunks:
                # Format chunks for context
                chunks_context = "\n\n".join([
                    f"Document chunk {i+1}:\n{chunk['text_content']}" 
                    for i, chunk in enumerate(retrieved_chunks)
                ])
                
                # Extract references
                for chunk in retrieved_chunks:
                    metadata = json.loads(chunk['source_metadata']) if isinstance(chunk['source_metadata'], str) else chunk['source_metadata']
                    source = metadata.get('source', 'Unknown source')
                    if source not in references:
                        references.append(source)
                
                # Add retrieval context to the user message
                enhanced_message = f"{message}\n\nRelevant context from documents:\n{chunks_context}"
                messages.append({"role": "user", "content": enhanced_message})
                
                # Format chunks for storage
                chunks = [
                    {
                        "id": chunk["id"],
                        "text": chunk["text_content"],
                        "source": json.loads(chunk["source_metadata"])["source"] if isinstance(chunk["source_metadata"], str) 
                                 else chunk["source_metadata"]["source"],
                        "similarity": float(chunk["similarity"])
                    } for chunk in retrieved_chunks
                ]
            else:
                messages.append({"role": "user", "content": message})
        else:
            messages.append({"role": "user", "content": message})
        
        # Generate response
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )
        
        return {
            "response": response.choices[0].message.content.strip(),
            "references": references,
            "chunks": chunks
        }