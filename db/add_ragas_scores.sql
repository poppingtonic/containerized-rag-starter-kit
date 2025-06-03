-- Add RAGAS scores column to query_cache table
ALTER TABLE query_cache 
ADD COLUMN IF NOT EXISTS ragas_scores JSONB;