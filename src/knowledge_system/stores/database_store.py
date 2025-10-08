"""
Database-backed Knowledge Store

Uses the shared Consilience PostgreSQL database with pgvector for:
- Vector embeddings storage
- Similarity search
- Document chunk storage

This allows multiple knowledge stores to share the same database
while maintaining logical separation through store_id partitioning.
"""

import logging
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
import openai

from .base import (
    KnowledgeStore,
    StoreMetadata,
    QueryResult,
    DocumentMetadata,
)

logger = logging.getLogger(__name__)


class DatabaseBackedStore(KnowledgeStore):
    """
    Knowledge store backed by PostgreSQL + pgvector.

    Shares the Consilience database but partitions data by store_id.
    Uses existing tables:
    - document_chunks: Stores text chunks with store_id
    - chunk_embeddings: Stores vectors with store_id

    Benefits:
    - Reuses existing vector search infrastructure
    - No duplicate embedding storage
    - Unified backup/recovery
    - Consistent query interface
    """

    def __init__(
        self,
        metadata: StoreMetadata,
        db_connection_string: str,
        openai_api_key: str
    ):
        super().__init__(metadata)
        self.db_connection_string = db_connection_string
        self.openai_api_key = openai_api_key
        self.db_pool = None
        openai.api_key = openai_api_key

    async def initialize(self) -> bool:
        """Initialize database connection and create store partition if needed"""
        try:
            # Create connection pool (simplified - production would use proper pooling)
            import psycopg2.pool
            self.db_pool = psycopg2.pool.SimpleConnectionPool(
                1, 10,
                self.db_connection_string
            )

            # Verify tables exist
            conn = self.db_pool.getconn()
            cur = conn.cursor()

            # Check if document_chunks table has store_id column
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='document_chunks' AND column_name='store_id'
            """)

            if not cur.fetchone():
                # Add store_id column if it doesn't exist
                logger.info("Adding store_id column to document_chunks")
                cur.execute("""
                    ALTER TABLE document_chunks
                    ADD COLUMN IF NOT EXISTS store_id VARCHAR(255) DEFAULT 'default'
                """)
                conn.commit()

            # Create index on store_id for efficient filtering
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_store_id
                ON document_chunks(store_id)
            """)
            conn.commit()

            cur.close()
            self.db_pool.putconn(conn)

            self._initialized = True
            logger.info(f"Initialized database store: {self.metadata.store_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize database store: {str(e)}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Check database connection health"""
        if not self._initialized or not self.db_pool:
            return {"healthy": False, "error": "Not initialized"}

        try:
            conn = self.db_pool.getconn()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            self.db_pool.putconn(conn)

            return {
                "healthy": True,
                "store_id": self.metadata.store_id,
                "store_type": self.metadata.store_type.value
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def index_document(
        self,
        doc_id: str,
        content: str,
        metadata: DocumentMetadata
    ) -> bool:
        """Index a document into the store"""
        if not self._initialized:
            raise RuntimeError("Store not initialized")

        try:
            # Chunk the content
            chunks = self._chunk_text(content, chunk_size=512, overlap=50)

            # Generate embeddings for each chunk
            embeddings = await self._generate_embeddings(chunks)

            conn = self.db_pool.getconn()
            cur = conn.cursor()

            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_id = f"{doc_id}_chunk_{i}"
                content_hash = hashlib.sha256(chunk.encode()).hexdigest()

                # Insert chunk
                cur.execute("""
                    INSERT INTO document_chunks (
                        chunk_id, source_file, content, chunk_index,
                        content_hash, store_id, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (chunk_id) DO UPDATE
                    SET content = EXCLUDED.content,
                        store_id = EXCLUDED.store_id,
                        created_at = EXCLUDED.created_at
                """, (
                    chunk_id,
                    metadata.title,
                    chunk,
                    i,
                    content_hash,
                    self.metadata.store_id,  # Partition by store_id
                    metadata.created_at or datetime.utcnow()
                ))

                # Insert embedding
                cur.execute("""
                    INSERT INTO chunk_embeddings (
                        chunk_id, embedding
                    ) VALUES (%s, %s)
                    ON CONFLICT (chunk_id) DO UPDATE
                    SET embedding = EXCLUDED.embedding
                """, (chunk_id, embedding))

            conn.commit()
            cur.close()
            self.db_pool.putconn(conn)

            logger.info(f"Indexed document {doc_id} with {len(chunks)} chunks in store {self.metadata.store_id}")
            return True

        except Exception as e:
            logger.error(f"Error indexing document: {str(e)}")
            return False

    async def query(
        self,
        query_text: str,
        user_id: str,
        user_roles: List[str],
        max_results: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[QueryResult]:
        """Query the store using vector similarity search"""
        if not self._initialized:
            raise RuntimeError("Store not initialized")

        try:
            # Generate query embedding
            query_embedding = await self._generate_embedding(query_text)

            conn = self.db_pool.getconn()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Vector similarity search filtered by store_id
            cur.execute("""
                SELECT
                    c.chunk_id,
                    c.source_file,
                    c.content,
                    c.chunk_index,
                    c.store_id,
                    c.created_at,
                    (e.embedding <=> %s::vector) as distance
                FROM document_chunks c
                JOIN chunk_embeddings e ON c.chunk_id = e.chunk_id
                WHERE c.store_id = %s
                ORDER BY e.embedding <=> %s::vector
                LIMIT %s
            """, (query_embedding, self.metadata.store_id, query_embedding, max_results))

            results = cur.fetchall()
            cur.close()
            self.db_pool.putconn(conn)

            # Convert to QueryResult objects
            query_results = []
            for row in results:
                # Check permissions (simplified - would use actual permission logic)
                if not await self.check_permission(row["chunk_id"], user_id, user_roles):
                    continue

                doc_metadata = DocumentMetadata(
                    doc_id=row["chunk_id"],
                    store_id=self.metadata.store_id,
                    title=row["source_file"],
                    author=None,
                    created_at=row["created_at"],
                    updated_at=row["created_at"],
                    tags=[],
                    permissions={},
                    sensitivity_level=self.metadata.pii_level,
                    content_hash="",
                    size_bytes=len(row["content"]),
                    custom_metadata={}
                )

                query_result = QueryResult(
                    doc_id=row["chunk_id"],
                    store_id=self.metadata.store_id,
                    content=row["content"],
                    metadata=doc_metadata,
                    similarity_score=1.0 - float(row["distance"]),  # Convert distance to similarity
                    chunks=[],
                    entities=[],
                    obfuscated=False
                )

                query_results.append(query_result)

            return query_results

        except Exception as e:
            logger.error(f"Error querying store: {str(e)}")
            return []

    async def get_document(
        self,
        doc_id: str,
        user_id: str,
        user_roles: List[str]
    ) -> Optional[QueryResult]:
        """Get a specific document by ID"""
        if not self._initialized:
            raise RuntimeError("Store not initialized")

        try:
            conn = self.db_pool.getconn()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                SELECT
                    c.chunk_id,
                    c.source_file,
                    c.content,
                    c.chunk_index,
                    c.store_id,
                    c.created_at
                FROM document_chunks c
                WHERE c.chunk_id = %s AND c.store_id = %s
            """, (doc_id, self.metadata.store_id))

            row = cur.fetchone()
            cur.close()
            self.db_pool.putconn(conn)

            if not row:
                return None

            # Check permissions
            if not await self.check_permission(doc_id, user_id, user_roles):
                return None

            doc_metadata = DocumentMetadata(
                doc_id=row["chunk_id"],
                store_id=self.metadata.store_id,
                title=row["source_file"],
                author=None,
                created_at=row["created_at"],
                updated_at=row["created_at"],
                tags=[],
                permissions={},
                sensitivity_level=self.metadata.pii_level,
                content_hash="",
                size_bytes=len(row["content"]),
                custom_metadata={}
            )

            return QueryResult(
                doc_id=row["chunk_id"],
                store_id=self.metadata.store_id,
                content=row["content"],
                metadata=doc_metadata,
                similarity_score=1.0,
                chunks=[],
                entities=[],
                obfuscated=False
            )

        except Exception as e:
            logger.error(f"Error getting document: {str(e)}")
            return None

    async def check_permission(
        self,
        doc_id: str,
        user_id: str,
        user_roles: List[str],
        operation: str = "read"
    ) -> bool:
        """Check if user has permission to access document"""
        # Check store-level permissions
        required_roles = self.metadata.requires_roles
        if not required_roles:
            return True

        return any(role in user_roles for role in required_roles)

    async def list_documents(
        self,
        user_id: str,
        user_roles: List[str],
        limit: int = 100,
        offset: int = 0
    ) -> List[DocumentMetadata]:
        """List documents in the store"""
        if not self._initialized:
            raise RuntimeError("Store not initialized")

        try:
            conn = self.db_pool.getconn()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                SELECT DISTINCT
                    source_file,
                    MIN(created_at) as created_at,
                    COUNT(*) as chunk_count
                FROM document_chunks
                WHERE store_id = %s
                GROUP BY source_file
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, (self.metadata.store_id, limit, offset))

            rows = cur.fetchall()
            cur.close()
            self.db_pool.putconn(conn)

            return [
                DocumentMetadata(
                    doc_id=row["source_file"],
                    store_id=self.metadata.store_id,
                    title=row["source_file"],
                    author=None,
                    created_at=row["created_at"],
                    updated_at=row["created_at"],
                    tags=[],
                    permissions={},
                    sensitivity_level=self.metadata.pii_level,
                    content_hash="",
                    size_bytes=0,
                    custom_metadata={"chunk_count": row["chunk_count"]}
                )
                for row in rows
            ]

        except Exception as e:
            logger.error(f"Error listing documents: {str(e)}")
            return []

    async def get_statistics(self) -> Dict[str, Any]:
        """Get store statistics"""
        if not self._initialized:
            return {"error": "Store not initialized"}

        try:
            conn = self.db_pool.getconn()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                SELECT
                    COUNT(DISTINCT source_file) as document_count,
                    COUNT(*) as chunk_count,
                    MIN(created_at) as oldest_document,
                    MAX(created_at) as newest_document
                FROM document_chunks
                WHERE store_id = %s
            """, (self.metadata.store_id,))

            stats = cur.fetchone()
            cur.close()
            self.db_pool.putconn(conn)

            return dict(stats) if stats else {}

        except Exception as e:
            logger.error(f"Error getting statistics: {str(e)}")
            return {"error": str(e)}

    # Helper methods

    def _chunk_text(self, text: str, chunk_size: int = 512, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks"""
        words = text.split()
        chunks = []

        for i in range(0, len(words), chunk_size - overlap):
            chunk = ' '.join(words[i:i + chunk_size])
            if chunk:
                chunks.append(chunk)

        return chunks

    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        try:
            response = openai.Embedding.create(
                model="text-embedding-ada-002",
                input=text
            )
            return response['data'][0]['embedding']
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise

    async def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        try:
            response = openai.Embedding.create(
                model="text-embedding-ada-002",
                input=texts
            )
            return [item['embedding'] for item in response['data']]
        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            raise
