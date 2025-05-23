-- Create user feedback and favorites table
CREATE TABLE IF NOT EXISTS user_feedback (
    id SERIAL PRIMARY KEY,
    query_cache_id INTEGER REFERENCES query_cache(id) ON DELETE CASCADE,
    feedback_text TEXT,
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    is_favorite BOOLEAN DEFAULT FALSE,
    has_thread BOOLEAN DEFAULT FALSE,
    thread_title TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index on favorites for quick retrieval
CREATE INDEX IF NOT EXISTS idx_user_feedback_favorite ON user_feedback(is_favorite) WHERE is_favorite = TRUE;

-- Create index on threads
CREATE INDEX IF NOT EXISTS idx_user_feedback_thread ON user_feedback(has_thread) WHERE has_thread = TRUE;

-- Create thread messages table
CREATE TABLE IF NOT EXISTS thread_messages (
    id SERIAL PRIMARY KEY,
    feedback_id INTEGER REFERENCES user_feedback(id) ON DELETE CASCADE,
    message_text TEXT NOT NULL,
    is_user BOOLEAN NOT NULL,
    "references" JSONB,
    chunk_ids JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index for retrieving thread messages
CREATE INDEX IF NOT EXISTS idx_thread_messages_feedback ON thread_messages(feedback_id);