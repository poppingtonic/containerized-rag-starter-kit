#!/usr/bin/env python3
"""
MCP Server for Consilience system.
Exposes query and document ingestion capabilities via Model Context Protocol.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
import os
import sys

# Add parent directory to path to import from api_service
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    BlobResourceContents,
    TextResourceContents
)

# Import services from the main API
from api_service.services.qa_service import QAService
from api_service.services.query_service import QueryService
from api_service.services.memory_service import MemoryService
from api_service.services.graph_service import GraphService
from api_service.utils.config import Config
from api_service.utils.database import get_db_pool

import aiohttp
import psycopg2
from psycopg2.extras import RealDictCursor

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConsilienceMCPServer:
    """MCP Server implementation for Consilience system."""
    
    def __init__(self):
        self.server = Server("consilience-mcp")
        self.qa_service = QAService()
        self.query_service = QueryService()
        self.memory_service = MemoryService()
        self.graph_service = GraphService()
        self.ingestion_url = os.getenv("INGESTION_SERVICE_URL", "http://ingestion-service:5050")
        
        # Register handlers
        self.server.list_tools.add_handler(self.handle_list_tools)
        self.server.call_tool.add_handler(self.handle_call_tool)
        
    async def handle_list_tools(self) -> List[Tool]:
        """Return list of available tools."""
        return [
            Tool(
                name="query_documents",
                description="Query the document database with filtered results",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The query to search for"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results to return",
                            "default": 5
                        },
                        "use_memory": {
                            "type": "boolean",
                            "description": "Whether to use cached results from memory",
                            "default": True
                        },
                        "use_amplification": {
                            "type": "boolean",
                            "description": "Use query amplification for better results",
                            "default": False
                        },
                        "use_smart_selection": {
                            "type": "boolean",
                            "description": "Use smart chunk selection",
                            "default": True
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="simple_query",
                description="Perform a simple query without advanced features",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The query to search for"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="trigger_ingestion",
                description="Trigger document ingestion process",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="ingestion_status",
                description="Get the current status of document ingestion",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="process_file",
                description="Process a specific file",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file to process"
                        }
                    },
                    "required": ["file_path"]
                }
            ),
            Tool(
                name="get_ingestion_progress",
                description="Get detailed ingestion progress from database",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="list_documents",
                description="List all documents in the database",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of documents to return",
                            "default": 20
                        }
                    }
                }
            ),
            Tool(
                name="get_memory_stats",
                description="Get memory/cache statistics",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="clear_memory",
                description="Clear the query memory cache",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            )
        ]
    
    async def handle_call_tool(self, name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """Handle tool calls."""
        try:
            if name == "query_documents":
                result = await self._query_documents(arguments)
            elif name == "simple_query":
                result = await self._simple_query(arguments)
            elif name == "trigger_ingestion":
                result = await self._trigger_ingestion()
            elif name == "ingestion_status":
                result = await self._get_ingestion_status()
            elif name == "process_file":
                result = await self._process_file(arguments)
            elif name == "get_ingestion_progress":
                result = await self._get_ingestion_progress()
            elif name == "list_documents":
                result = await self._list_documents(arguments)
            elif name == "get_memory_stats":
                result = await self._get_memory_stats()
            elif name == "clear_memory":
                result = await self._clear_memory()
            else:
                raise ValueError(f"Unknown tool: {name}")
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
            
        except Exception as e:
            logger.error(f"Error handling tool {name}: {str(e)}")
            return [TextContent(
                type="text", 
                text=json.dumps({"error": str(e)}, indent=2)
            )]
    
    async def _query_documents(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a document query with GraphRAG enhancement."""
        query = args["query"]
        max_results = args.get("max_results", 5)
        use_memory = args.get("use_memory", True)
        use_amplification = args.get("use_amplification", False)
        use_smart_selection = args.get("use_smart_selection", True)
        
        # Create query embedding
        query_embedding = self.query_service.create_embedding(query)
        
        # Check memory if enabled
        if Config.ENABLE_MEMORY and use_memory:
            memory_result = self.memory_service.check_memory(query, query_embedding)
            if memory_result:
                return memory_result
        
        # Perform vector search
        all_chunks = self.query_service.vector_search(query_embedding, max_results * 2)
        
        # Smart chunk selection
        if use_smart_selection and len(all_chunks) > max_results:
            selected_chunks = await self.qa_service.smart_chunk_selection(
                all_chunks, query, max_results
            )
        else:
            selected_chunks = all_chunks[:max_results]
        
        # Load graph data
        entities, communities = self.graph_service.enhance_with_graph(selected_chunks)
        
        # Generate answer
        answer, subquestions_data, verification_score = await self.qa_service.answer_generation(
            query, 
            selected_chunks, 
            use_amplification=use_amplification
        )
        
        # Format response
        result = {
            "query": query,
            "answer": answer,
            "chunks": [
                {
                    "content": chunk["content"],
                    "source": chunk.get("source_file", "Unknown"),
                    "chunk_index": chunk.get("chunk_index", -1),
                    "similarity": float(chunk.get("similarity", 0))
                }
                for chunk in selected_chunks
            ],
            "entities": [
                {
                    "name": entity["name"],
                    "type": entity["type"],
                    "description": entity.get("description", "")
                }
                for entity in entities
            ],
            "subquestions": subquestions_data,
            "verification_score": verification_score
        }
        
        # Save to memory if enabled
        if Config.ENABLE_MEMORY:
            self.memory_service.save_to_memory(query, query_embedding, result)
        
        return result
    
    async def _simple_query(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a simple query without advanced features."""
        query = args["query"]
        max_results = args.get("max_results", 5)
        
        # Create embedding and search
        query_embedding = self.query_service.create_embedding(query)
        chunks = self.query_service.vector_search(query_embedding, max_results)
        
        # Simple answer generation
        context = "\n\n".join([chunk["content"] for chunk in chunks])
        answer = self.query_service.generate_simple_answer(query, context)
        
        return {
            "query": query,
            "answer": answer,
            "chunks": [
                {
                    "content": chunk["content"],
                    "source": chunk.get("source_file", "Unknown"),
                    "similarity": float(chunk.get("similarity", 0))
                }
                for chunk in chunks
            ]
        }
    
    async def _trigger_ingestion(self) -> Dict[str, Any]:
        """Trigger document ingestion."""
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.ingestion_url}/trigger-ingestion") as response:
                return await response.json()
    
    async def _get_ingestion_status(self) -> Dict[str, Any]:
        """Get ingestion service status."""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.ingestion_url}/status") as response:
                return await response.json()
    
    async def _process_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Process a specific file."""
        file_path = args["file_path"]
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.ingestion_url}/process-file",
                json={"file_path": file_path}
            ) as response:
                return await response.json()
    
    async def _get_ingestion_progress(self) -> Dict[str, Any]:
        """Get detailed ingestion progress from database."""
        try:
            pool = get_db_pool()
            conn = pool.getconn()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get document chunk statistics
            cur.execute("""
                SELECT 
                    COUNT(DISTINCT source_file) as total_documents,
                    COUNT(*) as total_chunks,
                    MIN(created_at) as oldest_chunk,
                    MAX(created_at) as newest_chunk
                FROM document_chunks
            """)
            stats = cur.fetchone()
            
            # Get recent documents
            cur.execute("""
                SELECT 
                    source_file,
                    COUNT(*) as chunk_count,
                    MAX(created_at) as processed_at
                FROM document_chunks
                GROUP BY source_file
                ORDER BY MAX(created_at) DESC
                LIMIT 10
            """)
            recent_docs = cur.fetchall()
            
            cur.close()
            pool.putconn(conn)
            
            return {
                "statistics": dict(stats) if stats else {},
                "recent_documents": [dict(doc) for doc in recent_docs]
            }
            
        except Exception as e:
            logger.error(f"Database error: {str(e)}")
            return {"error": str(e)}
    
    async def _list_documents(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List all documents in the database."""
        limit = args.get("limit", 20)
        
        try:
            pool = get_db_pool()
            conn = pool.getconn()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("""
                SELECT 
                    source_file,
                    COUNT(*) as chunk_count,
                    MIN(created_at) as first_processed,
                    MAX(created_at) as last_processed
                FROM document_chunks
                GROUP BY source_file
                ORDER BY source_file
                LIMIT %s
            """, (limit,))
            
            documents = cur.fetchall()
            
            cur.close()
            pool.putconn(conn)
            
            return {
                "documents": [dict(doc) for doc in documents],
                "count": len(documents)
            }
            
        except Exception as e:
            logger.error(f"Database error: {str(e)}")
            return {"error": str(e)}
    
    async def _get_memory_stats(self) -> Dict[str, Any]:
        """Get memory/cache statistics."""
        try:
            pool = get_db_pool()
            conn = pool.getconn()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("""
                SELECT 
                    COUNT(*) as total_cached_queries,
                    AVG(LENGTH(result::text)) as avg_result_size,
                    MIN(created_at) as oldest_cache_entry,
                    MAX(created_at) as newest_cache_entry
                FROM query_cache
            """)
            
            stats = cur.fetchone()
            
            cur.close()
            pool.putconn(conn)
            
            return dict(stats) if stats else {"message": "No cached queries found"}
            
        except Exception as e:
            logger.error(f"Database error: {str(e)}")
            return {"error": str(e)}
    
    async def _clear_memory(self) -> Dict[str, Any]:
        """Clear the query memory cache."""
        try:
            pool = get_db_pool()
            conn = pool.getconn()
            cur = conn.cursor()
            
            cur.execute("DELETE FROM query_cache")
            deleted_count = cur.rowcount
            
            conn.commit()
            cur.close()
            pool.putconn(conn)
            
            return {
                "status": "success",
                "deleted_queries": deleted_count,
                "message": f"Cleared {deleted_count} cached queries"
            }
            
        except Exception as e:
            logger.error(f"Database error: {str(e)}")
            return {"error": str(e)}
    
    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream)

def main():
    """Main entry point."""
    server = ConsilienceMCPServer()
    asyncio.run(server.run())

if __name__ == "__main__":
    main()