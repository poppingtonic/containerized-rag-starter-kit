import os
import json
import time
import psycopg2
import networkx as nx
import spacy
import pandas as pd
import numpy as np
from openai import OpenAI
import jsonlines
from datetime import datetime

# Configuration from environment variables
DB_URL = os.environ.get("DATABASE_URL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/app/outputs")
PROCESSING_INTERVAL = int(os.environ.get("PROCESSING_INTERVAL", "3600"))  # Default: 1 hour

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize spaCy for NER
try:
    nlp = spacy.load("en_core_web_sm")
except:
    spacy.cli.download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

# Database connection
def get_db_connection():
    return psycopg2.connect(DB_URL)

# Fetch chunks and embeddings from database
def fetch_data():
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    dc.id, 
                    dc.text_content, 
                    dc.source_metadata, 
                    ce.embedding_vector 
                FROM 
                    document_chunks dc
                JOIN 
                    chunk_embeddings ce ON dc.id = ce.chunk_id
            """)
            
            # Return list of (id, text, metadata, embedding)
            return cursor.fetchall()

# Extract entities from text using spaCy
def extract_entities(text):
    doc = nlp(text)
    entities = {}
    
    for ent in doc.ents:
        entity_type = ent.label_
        entity_text = ent.text
        
        if entity_type not in entities:
            entities[entity_type] = []
        
        if entity_text not in entities[entity_type]:
            entities[entity_type].append(entity_text)
    
    return entities

# Create knowledge graph
def build_knowledge_graph(chunks_data):
    G = nx.Graph()
    
    # Add nodes for chunks
    for chunk_id, text, metadata, _ in chunks_data:
        metadata_dict = json.loads(metadata) if isinstance(metadata, str) else metadata
        G.add_node(f"chunk_{chunk_id}", 
                   type="chunk", 
                   text=text[:100] + "...", 
                   source=metadata_dict.get("source", "unknown"))
        
        # Extract entities
        entities = extract_entities(text)
        
        # Add entity nodes and connect to chunks
        for entity_type, entity_list in entities.items():
            for entity in entity_list:
                entity_id = f"{entity_type}_{entity}"
                
                # Add entity node if it doesn't exist
                if not G.has_node(entity_id):
                    G.add_node(entity_id, type="entity", entity_type=entity_type, text=entity)
                
                # Connect entity to chunk
                G.add_edge(f"chunk_{chunk_id}", entity_id, weight=1)
    
    # Add edges between entities that appear in the same chunks
    entity_nodes = [n for n, attr in G.nodes(data=True) if attr["type"] == "entity"]
    for i, entity1 in enumerate(entity_nodes):
        for entity2 in entity_nodes[i+1:]:
            # Get common neighbors (chunks)
            common_chunks = list(nx.common_neighbors(G, entity1, entity2))
            if common_chunks:
                # Weight by number of common chunks
                G.add_edge(entity1, entity2, weight=len(common_chunks))
    
    return G

# Generate summaries for entity communities using LLM
def generate_entity_summaries(G, chunks_data):
    # Detect communities using Louvain method
    try:
        import community as community_louvain
        partition = community_louvain.best_partition(G)
    except ImportError:
        # Fallback to a simpler approach
        from networkx.algorithms import community
        partition = {}
        communities = list(community.greedy_modularity_communities(G))
        for i, comm in enumerate(communities):
            for node in comm:
                partition[node] = i
    
    # Group nodes by community
    communities = {}
    for node, community_id in partition.items():
        if community_id not in communities:
            communities[community_id] = []
        communities[community_id].append(node)
    
    # Generate summaries for each significant community
    summaries = []
    for community_id, nodes in communities.items():
        # Only process communities with at least 3 nodes
        if len(nodes) < 3:
            continue
        
        # Get entity nodes in this community
        entity_nodes = [n for n in nodes if G.nodes[n]["type"] == "entity"]
        if not entity_nodes:
            continue
        
        # Get chunk nodes connected to these entities
        chunk_texts = []
        for entity_node in entity_nodes:
            for neighbor in G.neighbors(entity_node):
                if G.nodes[neighbor]["type"] == "chunk":
                    # Get original text
                    chunk_id = int(neighbor.replace("chunk_", ""))
                    for c_id, text, _, _ in chunks_data:
                        if c_id == chunk_id:
                            chunk_texts.append(text)
                            break
        
        # Prepare context for the summary
        entity_info = [f"{G.nodes[n]['text']} ({G.nodes[n]['entity_type']})" for n in entity_nodes]
        context = "\n".join(chunk_texts[:5])  # Limit to first 5 chunks to avoid token limits
        
        # Generate summary with OpenAI
        prompt = f"""
        Generate a concise summary about the following entities based on the provided context.
        
        Entities:
        {', '.join(entity_info)}
        
        Context:
        {context}
        
        Provide a 2-3 sentence summary that explains the relationships between these entities and their significance.
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that creates concise summaries."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.5
        )
        
        summary = response.choices[0].message.content.strip()
        summaries.append({
            "community_id": community_id,
            "entities": entity_info,
            "summary": summary,
            "related_chunks": [int(n.replace("chunk_", "")) for n in nodes if G.nodes[n]["type"] == "chunk"]
        })
    
    return summaries

# Save graph and summaries
def save_outputs(G, summaries):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Save graph as edge list
    edges_file = os.path.join(OUTPUT_DIR, f"graph_edges_{timestamp}.csv")
    with open(edges_file, 'w') as f:
        f.write("source,target,weight,source_type,target_type\n")
        for source, target, data in G.edges(data=True):
            source_type = G.nodes[source]["type"]
            target_type = G.nodes[target]["type"]
            f.write(f"{source},{target},{data.get('weight', 1)},{source_type},{target_type}\n")
    
    # Save node attributes
    nodes_file = os.path.join(OUTPUT_DIR, f"graph_nodes_{timestamp}.csv")
    with open(nodes_file, 'w') as f:
        f.write("id,type,entity_type,text,source\n")
        for node, attrs in G.nodes(data=True):
            node_type = attrs.get("type", "")
            entity_type = attrs.get("entity_type", "")
            text = attrs.get("text", "").replace(",", " ").replace("\n", " ")
            source = attrs.get("source", "")
            f.write(f"{node},{node_type},{entity_type},{text},{source}\n")
    
    # Save summaries
    summaries_file = os.path.join(OUTPUT_DIR, f"summaries_{timestamp}.jsonl")
    with jsonlines.open(summaries_file, mode='w') as writer:
        for summary in summaries:
            writer.write(summary)
    
    # Save latest reference file for the API service
    latest_refs = {
        "edges": edges_file,
        "nodes": nodes_file,
        "summaries": summaries_file,
        "timestamp": timestamp
    }
    
    with open(os.path.join(OUTPUT_DIR, "latest_refs.json"), 'w') as f:
        json.dump(latest_refs, f, indent=2)
    
    print(f"Saved graph with {len(G.nodes())} nodes and {len(G.edges())} edges")
    print(f"Generated {len(summaries)} community summaries")

# Main processing function
def process_graph():
    print("Starting GraphRAG processing...")
    
    # Fetch data
    chunks_data = fetch_data()
    if not chunks_data:
        print("No data to process")
        return
    
    print(f"Fetched {len(chunks_data)} document chunks")
    
    # Build graph
    G = build_knowledge_graph(chunks_data)
    
    # Generate summaries
    summaries = generate_entity_summaries(G)
    
    # Save outputs
    save_outputs(G, summaries)
    
    print("GraphRAG processing completed")

# Main function
def main():
    # Initial processing
    process_graph()
    
    # Periodic processing
    while True:
        print(f"Waiting {PROCESSING_INTERVAL} seconds until next processing...")
        time.sleep(PROCESSING_INTERVAL)
        process_graph()

if __name__ == "__main__":
    # Wait for database and ingestion service to be ready
    time.sleep(10)
    main()