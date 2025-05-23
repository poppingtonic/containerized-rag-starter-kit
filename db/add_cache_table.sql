-- Create query memory table
CREATE TABLE IF NOT EXISTS query_cache (
    id SERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    query_embedding VECTOR(1536),
    answer_text TEXT NOT NULL,
    "references" JSONB,
    chunk_ids JSONB,
    entities JSONB,
    communities JSONB,
    access_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index on query text for direct lookups
CREATE INDEX IF NOT EXISTS idx_query_cache_text ON query_cache(query_text);

-- Create index for vector similarity search on remembered queries
CREATE INDEX IF NOT EXISTS idx_query_cache_embedding ON query_cache USING ivfflat (query_embedding vector_cosine_ops);