-- Data migration script to populate document table from existing document_chunks
-- This handles the case where document_chunks already exists but document table is new

BEGIN;

-- First, let's see what we're working with
-- SELECT COUNT(*) as total_chunks FROM document_chunks;
-- SELECT COUNT(DISTINCT source_metadata->>'source') as unique_sources FROM document_chunks;

-- Step 1: Create document table if it doesn't exist (from add_document_table.sql)
CREATE TABLE IF NOT EXISTS document (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL UNIQUE,
    file_path TEXT NOT NULL,
    content_hash VARCHAR(64) UNIQUE,  -- SHA-256 hash for deduplication
    file_size BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Citation metadata (populated by DOI fetcher)
    doi VARCHAR(255),
    reference TEXT,  -- APA-formatted citation from doi.org citation API
    
    -- Processing status
    citation_fetched BOOLEAN DEFAULT FALSE,
    citation_fetch_attempted_at TIMESTAMP,
    citation_fetch_error TEXT,
    
    CONSTRAINT valid_doi CHECK (doi IS NULL OR doi ~ '^10\.\d{4,}/.*$')
);

-- Step 2: Add document_id column to document_chunks if it doesn't exist
ALTER TABLE document_chunks 
ADD COLUMN IF NOT EXISTS document_id INTEGER REFERENCES document(id) ON DELETE CASCADE;

-- Step 3: Create a temporary function to extract DOI from filename
CREATE OR REPLACE FUNCTION extract_doi_from_filename(filename TEXT) RETURNS TEXT AS $$
BEGIN
    -- Remove file extension and path
    filename := regexp_replace(filename, '\.[^.]*$', '');  -- Remove extension
    filename := regexp_replace(filename, '^.*/', '');      -- Remove path
    
    -- Check if filename looks like a DOI (starts with 10. and has hyphens)
    IF filename ~ '^10\.\d+' AND position('-' in filename) > 0 THEN
        -- Convert first hyphen to forward slash to create DOI
        filename := regexp_replace(filename, '-', '/', '');
        -- Validate DOI format
        IF filename ~ '^10\.\d{4,}/' THEN
            RETURN filename;
        END IF;
    END IF;
    
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Step 4: Insert unique documents from document_chunks
INSERT INTO document (filename, file_path, content_hash, doi, created_at)
SELECT DISTINCT
    source_metadata->>'source' as filename,
    COALESCE(source_metadata->>'path', source_metadata->>'source') as file_path,
    source_metadata->>'content_hash' as content_hash,
    extract_doi_from_filename(source_metadata->>'source') as doi,
    MIN((source_metadata->>'processed_at')::timestamp) as created_at
FROM document_chunks 
WHERE source_metadata->>'source' IS NOT NULL
  AND source_metadata->>'source' != ''
GROUP BY 
    source_metadata->>'source',
    source_metadata->>'path', 
    source_metadata->>'content_hash'
ON CONFLICT (filename) DO NOTHING;  -- Skip if already exists

-- Step 5: Update document_chunks with document_id foreign keys
UPDATE document_chunks 
SET document_id = d.id
FROM document d
WHERE d.filename = document_chunks.source_metadata->>'source'
  AND document_chunks.document_id IS NULL;

-- Step 6: Clean up temporary function
DROP FUNCTION IF EXISTS extract_doi_from_filename(TEXT);

-- Step 7: Create indexes for better performance (if they don't exist)
CREATE INDEX IF NOT EXISTS idx_document_filename ON document(filename);
CREATE INDEX IF NOT EXISTS idx_document_doi ON document(doi);
CREATE INDEX IF NOT EXISTS idx_document_content_hash ON document(content_hash);
CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id);

-- Step 8: Create update trigger for updated_at
CREATE OR REPLACE FUNCTION update_document_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- CREATE TRIGGER update_document_updated_at
--     BEFORE UPDATE ON document
--     FOR EACH ROW
--     EXECUTE FUNCTION update_document_updated_at();

-- Verification queries (uncomment to run)
-- SELECT 'Documents created:' as info, COUNT(*) as count FROM document;
-- SELECT 'Chunks with document_id:' as info, COUNT(*) as count FROM document_chunks WHERE document_id IS NOT NULL;
-- SELECT 'Chunks without document_id:' as info, COUNT(*) as count FROM document_chunks WHERE document_id IS NULL;
-- SELECT 'Documents with DOIs:' as info, COUNT(*) as count FROM document WHERE doi IS NOT NULL;

COMMIT;

-- If anything goes wrong, you can rollback with:
-- ROLLBACK;