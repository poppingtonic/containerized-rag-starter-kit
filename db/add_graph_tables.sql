-- Create tables for knowledge graph data

-- Table for graph nodes (entities and chunks)
CREATE TABLE IF NOT EXISTS graph_nodes (
    id SERIAL PRIMARY KEY,
    node_id VARCHAR(255) NOT NULL,
    node_type VARCHAR(50) NOT NULL, -- 'entity' or 'chunk'
    entity_type VARCHAR(100), -- For entities: PERSON, ORG, etc.
    text TEXT,
    source VARCHAR(255),
    processing_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(node_id, processing_timestamp)
);

-- Table for graph edges (relationships)
CREATE TABLE IF NOT EXISTS graph_edges (
    id SERIAL PRIMARY KEY,
    source_node VARCHAR(255) NOT NULL,
    target_node VARCHAR(255) NOT NULL,
    weight FLOAT DEFAULT 1.0,
    relation VARCHAR(255),
    source_type VARCHAR(50),
    target_type VARCHAR(50),
    processing_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table for community summaries
CREATE TABLE IF NOT EXISTS community_summaries (
    id SERIAL PRIMARY KEY,
    community_id INTEGER NOT NULL,
    summary TEXT NOT NULL,
    entities JSONB, -- Array of entity info
    key_relations JSONB, -- Array of key relations
    num_entities INTEGER,
    num_chunks INTEGER,
    processing_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_graph_nodes_node_id ON graph_nodes(node_id);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_type ON graph_nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_timestamp ON graph_nodes(processing_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_graph_edges_source ON graph_edges(source_node);
CREATE INDEX IF NOT EXISTS idx_graph_edges_target ON graph_edges(target_node);
CREATE INDEX IF NOT EXISTS idx_graph_edges_timestamp ON graph_edges(processing_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_community_summaries_timestamp ON community_summaries(processing_timestamp DESC);

-- Create a view for the latest graph data
CREATE OR REPLACE VIEW latest_graph_nodes AS
SELECT DISTINCT ON (node_id) *
FROM graph_nodes
ORDER BY node_id, processing_timestamp DESC;

CREATE OR REPLACE VIEW latest_graph_edges AS
SELECT DISTINCT ON (source_node, target_node, relation) *
FROM graph_edges
ORDER BY source_node, target_node, relation, processing_timestamp DESC;

CREATE OR REPLACE VIEW latest_community_summaries AS
SELECT *
FROM community_summaries
WHERE processing_timestamp = (SELECT MAX(processing_timestamp) FROM community_summaries);