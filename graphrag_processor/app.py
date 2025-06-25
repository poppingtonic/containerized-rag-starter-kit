import os
import json
import time
import psycopg2
import networkx as nx
import stanza
import pandas as pd
import numpy as np
from openai import OpenAI
import jsonlines
from datetime import datetime
from collections import defaultdict
from sentence_transformers import SentenceTransformer, util
from stanford_openie import StanfordOpenIE
import torch
import gc
from psycopg2.extras import RealDictCursor

# Configuration from environment variables
DB_URL = os.environ.get("DATABASE_URL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/app/outputs")
PROCESSING_INTERVAL = int(os.environ.get("PROCESSING_INTERVAL", "3600"))  # Default: 1 hour
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "100"))  # Process chunks in batches
MAX_TEXT_LENGTH = int(os.environ.get("MAX_TEXT_LENGTH", "5000"))  # Limit text length for processing

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize Stanza pipeline with all required processors
print("Initializing Stanza pipeline...")
stanza.download('en', verbose=False)  # Download models if not present
nlp = stanza.Pipeline('en', processors='tokenize,mwt,pos,lemma,ner,depparse,coref', verbose=False, use_gpu=torch.cuda.is_available())

# Initialize sentence transformer for entity linking
entity_linker_model = SentenceTransformer('all-MiniLM-L6-v2')

# Initialize Stanford OpenIE for relation extraction
openie_client = None

# Database connection
def get_db_connection():
    return psycopg2.connect(DB_URL)

# Get total number of chunks
def get_chunk_count():
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM document_chunks")
            return cursor.fetchone()[0]

# Fetch chunks in batches
def fetch_data_batch(offset, limit):
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
                ORDER BY dc.id
                LIMIT %s OFFSET %s
            """, (limit, offset))
            
            return cursor.fetchall()

# Process text with Stanza for NER and coreference resolution
def process_text_with_stanza(text):
    """
    Process text using Stanza to extract entities and resolve coreferences.
    Returns processed text and entity dictionary.
    """
    # Limit text length to avoid memory issues
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]
    
    try:
        # Process with Stanza
        doc = nlp(text)
        
        # Extract entities
        entities = defaultdict(list)
        for sent in doc.sentences:
            for ent in sent.ents:
                entity_type = ent.type
                entity_text = ent.text.strip()
                
                # Skip very short entities or those with non-alphanumeric characters only
                if len(entity_text) < 2 or not any(c.isalnum() for c in entity_text):
                    continue
                    
                if entity_text not in entities[entity_type]:
                    entities[entity_type].append(entity_text)
        
        # Process coreferences and create resolved text
        resolved_text = text
        if hasattr(doc, 'coref_chains') and doc.coref_chains:
            # Build a mapping of mention spans to their representative mention
            replacements = []
            
            for chain in doc.coref_chains:
                if len(chain) < 2:
                    continue
                    
                # Find the representative mention (prefer named entities)
                representative = None
                for mention in chain:
                    mention_text = mention.text
                    # Check if this mention is a named entity
                    for entity_type, entity_list in entities.items():
                        if mention_text in entity_list:
                            representative = mention_text
                            break
                    if representative:
                        break
                
                # If no named entity found, use the first mention
                if not representative:
                    representative = chain[0].text
                
                # Create replacements for all mentions except the representative
                for mention in chain:
                    if mention.text != representative:
                        # Store the replacement info
                        replacements.append({
                            'start': mention.start_char,
                            'end': mention.end_char,
                            'original': mention.text,
                            'replacement': representative
                        })
            
            # Apply replacements in reverse order to maintain character positions
            replacements.sort(key=lambda x: x['start'], reverse=True)
            for repl in replacements[:50]:  # Limit replacements to avoid excessive processing
                resolved_text = (
                    resolved_text[:repl['start']] + 
                    repl['replacement'] + 
                    resolved_text[repl['end']:]
                )
        
        return resolved_text, dict(entities)
    except Exception as e:
        print(f"Error processing text with Stanza: {e}")
        return text, {}

# Extract relations using Stanford OpenIE
def extract_relations_openie(text):
    """
    Extract relations from text using Stanford OpenIE.
    Returns a DataFrame with subject, relation, object triples.
    """
    global openie_client
    
    if openie_client is None:
        try:
            openie_client = StanfordOpenIE()
        except Exception as e:
            print(f"Failed to initialize OpenIE: {e}")
            return pd.DataFrame(columns=['subject', 'relation', 'object'])
    
    try:
        triples = []
        for triple in openie_client.annotate(text):
            triples.append({
                'subject': triple['subject'],
                'relation': triple['relation'],
                'object': triple['object']
            })
        return pd.DataFrame(triples)
    except Exception as e:
        print(f"Error extracting relations: {e}")
        return pd.DataFrame(columns=['subject', 'relation', 'object'])

# Extract relations using Stanza dependency parsing as fallback
def extract_relations_stanza(text, entities):
    """
    Extract relations from text using Stanza's dependency parsing.
    This is a simpler approach than OpenIE but works well for basic relations.
    """
    try:
        doc = nlp(text[:MAX_TEXT_LENGTH])  # Limit text length
        triples = []
        
        # Flatten entity list
        all_entities = set()
        for entity_list in entities.values():
            all_entities.update(entity_list)
        
        for sent in doc.sentences:
            # Look for subject-verb-object patterns
            for word in sent.words:
                if word.upos == 'VERB':
                    # Find subject and object
                    subject = None
                    obj = None
                    
                    for child in sent.words:
                        if child.head == word.id:
                            if child.deprel in ['nsubj', 'nsubj:pass']:
                                subject = child.text
                            elif child.deprel in ['obj', 'dobj', 'iobj']:
                                obj = child.text
                    
                    # Create triple if both subject and object found
                    if subject and obj:
                        triples.append({
                            'subject': subject,
                            'relation': word.text,
                            'object': obj
                        })
        
        return pd.DataFrame(triples)
    except Exception as e:
        print(f"Error in Stanza relation extraction: {e}")
        return pd.DataFrame(columns=['subject', 'relation', 'object'])

# Entity linking using sentence transformers
def link_entities(triple_df, confidence_threshold=0.85):
    """
    Link similar entities using sentence transformers.
    """
    if len(triple_df) == 0:
        return triple_df
    
    # Get all unique entities
    all_entities = set()
    all_entities.update(triple_df['subject'].unique())
    all_entities.update(triple_df['object'].unique())
    entity_list = list(all_entities)
    
    if len(entity_list) < 2:
        return triple_df
    
    # Process entities in smaller batches to avoid memory issues
    entity_mapping = {}
    batch_size = 500
    
    for i in range(0, len(entity_list), batch_size):
        batch = entity_list[i:i+batch_size]
        
        # Encode batch
        embeddings = entity_linker_model.encode(batch, convert_to_tensor=True)
        
        # Find similar entities within batch
        for j in range(len(batch)):
            if batch[j] in entity_mapping:
                continue
                
            for k in range(j + 1, len(batch)):
                if batch[k] in entity_mapping:
                    continue
                    
                similarity = util.pytorch_cos_sim(embeddings[j], embeddings[k])[0][0].item()
                
                if similarity > confidence_threshold:
                    # Use the shorter entity as the canonical form
                    if len(batch[j]) <= len(batch[k]):
                        entity_mapping[batch[k]] = batch[j]
                    else:
                        entity_mapping[batch[j]] = batch[k]
        
        # Clear GPU memory if using CUDA
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    
    # Apply entity mapping to the triple dataframe
    triple_df['subject'] = triple_df['subject'].map(lambda x: entity_mapping.get(x, x))
    triple_df['object'] = triple_df['object'].map(lambda x: entity_mapping.get(x, x))
    
    return triple_df.drop_duplicates()

# Save triples to database
def save_triples_to_db(triples_df, chunk_id):
    """Save extracted triples to database for later viewing."""
    if len(triples_df) == 0:
        return
        
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # Create table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entity_triples (
                    id SERIAL PRIMARY KEY,
                    chunk_id INTEGER REFERENCES document_chunks(id),
                    subject TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    object TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Insert triples
            for _, row in triples_df.iterrows():
                cursor.execute("""
                    INSERT INTO entity_triples (chunk_id, subject, relation, object)
                    VALUES (%s, %s, %s, %s)
                """, (chunk_id, row['subject'], row['relation'], row['object']))
            
            conn.commit()

# Create knowledge graph from processed data in batches
def build_knowledge_graph_incremental():
    """
    Build a knowledge graph from document chunks using batch processing.
    """
    G = nx.Graph()
    total_chunks = get_chunk_count()
    print(f"Total chunks to process: {total_chunks}")
    
    # Process chunks in batches
    for offset in range(0, total_chunks, BATCH_SIZE):
        print(f"Processing batch {offset//BATCH_SIZE + 1} of {(total_chunks + BATCH_SIZE - 1)//BATCH_SIZE}")
        
        # Fetch batch
        chunks_batch = fetch_data_batch(offset, BATCH_SIZE)
        
        for chunk_id, text, metadata, _ in chunks_batch:
            metadata_dict = json.loads(metadata) if isinstance(metadata, str) else metadata
            
            # Add chunk node
            G.add_node(f"chunk_{chunk_id}", 
                       type="chunk", 
                       text=text[:100] + "...", 
                       source=metadata_dict.get("source", "unknown"))
            
            # Process text with Stanza
            resolved_text, entities = process_text_with_stanza(text)
            
            # Extract relations (try OpenIE first, fallback to Stanza)
            try:
                relations_df = extract_relations_openie(resolved_text)
                if len(relations_df) == 0:
                    relations_df = extract_relations_stanza(resolved_text, entities)
            except:
                relations_df = extract_relations_stanza(resolved_text, entities)
            
            # Save triples to database
            save_triples_to_db(relations_df, chunk_id)
            
            # Add entities as nodes
            for entity_type, entity_list in entities.items():
                for entity in entity_list[:50]:  # Limit entities per chunk
                    entity_id = f"{entity_type}_{entity}"
                    
                    # Add entity node if it doesn't exist
                    if not G.has_node(entity_id):
                        G.add_node(entity_id, type="entity", entity_type=entity_type, text=entity)
                    
                    # Connect entity to chunk
                    G.add_edge(f"chunk_{chunk_id}", entity_id, weight=1, relation="contains")
            
            # Add relations as edges
            for _, row in relations_df.iterrows():
                # Create nodes for subject and object if they don't exist
                subj_id = f"ENTITY_{row['subject']}"
                obj_id = f"ENTITY_{row['object']}"
                
                if not G.has_node(subj_id):
                    G.add_node(subj_id, type="entity", entity_type="EXTRACTED", text=row['subject'])
                if not G.has_node(obj_id):
                    G.add_node(obj_id, type="entity", entity_type="EXTRACTED", text=row['object'])
                
                # Add relation edge
                G.add_edge(subj_id, obj_id, weight=1, relation=row['relation'])
                
                # Connect to chunk
                G.add_edge(f"chunk_{chunk_id}", subj_id, weight=0.5, relation="mentions")
                G.add_edge(f"chunk_{chunk_id}", obj_id, weight=0.5, relation="mentions")
        
        # Periodic cleanup
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        # Save intermediate graph state every 10 batches
        if (offset // BATCH_SIZE + 1) % 10 == 0:
            print(f"Saving intermediate graph state...")
            save_outputs(G, [])  # Save graph without summaries for now
    
    return G

# Generate summaries for entity communities using LLM
def generate_entity_summaries_batched(G):
    """
    Generate summaries for communities of entities in the graph.
    Process chunks from database in batches to avoid loading all into memory.
    """
    # Detect communities
    try:
        from networkx.algorithms import community
        communities = list(community.greedy_modularity_communities(G))
        
        # Convert to partition format
        partition = {}
        for i, comm in enumerate(communities):
            for node in comm:
                partition[node] = i
    except Exception as e:
        print(f"Community detection failed: {e}")
        # Fallback: put all entities in one community
        partition = {node: 0 for node in G.nodes()}
    
    # Group nodes by community
    communities = defaultdict(list)
    for node, community_id in partition.items():
        communities[community_id].append(node)
    
    # Generate summaries for each significant community
    summaries = []
    for community_id, nodes in communities.items():
        # Only process communities with at least 3 entity nodes
        entity_nodes = [n for n in nodes if G.nodes[n]["type"] == "entity"]
        if len(entity_nodes) < 3:
            continue
        
        # Get chunk IDs connected to these entities
        chunk_ids = set()
        for entity_node in entity_nodes:
            for neighbor in G.neighbors(entity_node):
                if G.nodes[neighbor]["type"] == "chunk":
                    chunk_id = int(neighbor.replace("chunk_", ""))
                    chunk_ids.add(chunk_id)
        
        if not chunk_ids:
            continue
        
        # Fetch chunk texts from database (limit to avoid memory issues)
        chunk_texts = []
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT text_content 
                    FROM document_chunks 
                    WHERE id = ANY(%s)
                    LIMIT 5
                """, (list(chunk_ids)[:5],))
                
                for row in cursor:
                    chunk_texts.append(row[0])
        
        if not chunk_texts:
            continue
        
        # Prepare entity information
        entity_info = []
        for n in entity_nodes[:20]:  # Limit to top 20 entities
            node_data = G.nodes[n]
            entity_info.append(f"{node_data['text']} ({node_data.get('entity_type', 'ENTITY')})")
        
        # Extract key relations for this community
        relations = []
        for n1 in entity_nodes:
            for n2 in G.neighbors(n1):
                if n2 in entity_nodes and G.has_edge(n1, n2):
                    edge_data = G[n1][n2]
                    if 'relation' in edge_data and edge_data['relation'] != 'contains':
                        relations.append(f"{G.nodes[n1]['text']} - {edge_data['relation']} - {G.nodes[n2]['text']}")
        
        # Generate summary with OpenAI
        context = "\n".join(chunk_texts[:3])  # Limit context to avoid token limits
        relations_text = "\n".join(relations[:10]) if relations else "No specific relations found."
        
        prompt = f"""
        Generate a concise summary about the following group of related entities based on the provided context.
        
        Key Entities:
        {', '.join(entity_info)}
        
        Key Relations:
        {relations_text}
        
        Context:
        {context[:2000]}
        
        Provide a 2-3 sentence summary that explains the main theme connecting these entities and their significance. Focus on the relationships and patterns you observe.
        """
        
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that creates concise summaries of entity relationships."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.5
            )
            
            summary = response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error generating summary: {e}")
            summary = f"Community of {len(entity_nodes)} entities including: {', '.join(entity_info[:5])}"
        
        summaries.append({
            "community_id": community_id,
            "entities": entity_info,
            "summary": summary,
            "num_entities": len(entity_nodes),
            "num_chunks": len(chunk_ids),
            "key_relations": relations[:5]
        })
    
    return summaries

# Save graph and summaries
def save_outputs(G, summaries):
    """
    Save the knowledge graph and community summaries.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Save graph as edge list with relation information
    edges_file = os.path.join(OUTPUT_DIR, f"graph_edges_{timestamp}.csv")
    with open(edges_file, 'w') as f:
        f.write("source,target,weight,relation,source_type,target_type\n")
        for source, target, data in G.edges(data=True):
            source_type = G.nodes[source]["type"]
            target_type = G.nodes[target]["type"]
            relation = data.get('relation', '')
            weight = data.get('weight', 1)
            f.write(f"{source},{target},{weight},{relation},{source_type},{target_type}\n")
    
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
    
    # Save summaries with extended information
    summaries_file = os.path.join(OUTPUT_DIR, f"summaries_{timestamp}.jsonl")
    with jsonlines.open(summaries_file, mode='w') as writer:
        for summary in summaries:
            writer.write(summary)
    
    # Save latest reference file for the API service
    latest_refs = {
        "edges": edges_file,
        "nodes": nodes_file,
        "summaries": summaries_file,
        "timestamp": timestamp,
        "num_nodes": len(G.nodes()),
        "num_edges": len(G.edges()),
        "num_communities": len(summaries)
    }
    
    with open(os.path.join(OUTPUT_DIR, "latest_refs.json"), 'w') as f:
        json.dump(latest_refs, f, indent=2)
    
    print(f"Saved graph with {len(G.nodes())} nodes and {len(G.edges())} edges")
    print(f"Generated {len(summaries)} community summaries")

# Create database view for triples
def create_triples_view():
    """Create a database view for easy access to entity triples."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE OR REPLACE VIEW entity_triples_view AS
                SELECT 
                    et.id,
                    et.chunk_id,
                    et.subject,
                    et.relation,
                    et.object,
                    et.created_at,
                    dc.source_metadata->>'source' as source_file,
                    dc.source_metadata->>'page' as page_number
                FROM entity_triples et
                JOIN document_chunks dc ON et.chunk_id = dc.id
                ORDER BY et.created_at DESC;
            """)
            
            # Create indexes for better performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_entity_triples_subject 
                ON entity_triples(subject);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_entity_triples_object 
                ON entity_triples(object);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_entity_triples_relation 
                ON entity_triples(relation);
            """)
            
            conn.commit()
            print("Created entity_triples_view for easy access to relationships")

# Main processing function
def process_graph():
    """
    Main function to process chunks and build knowledge graph.
    """
    print("Starting optimized GraphRAG processing...")
    
    # Create triples view if it doesn't exist
    create_triples_view()
    
    # Check if there's data to process
    total_chunks = get_chunk_count()
    if total_chunks == 0:
        print("No data to process")
        return
    
    print(f"Total chunks to process: {total_chunks}")
    
    # Build graph incrementally
    G = build_knowledge_graph_incremental()
    
    # Generate summaries with batched processing
    summaries = generate_entity_summaries_batched(G)
    
    # Save outputs
    save_outputs(G, summaries)
    
    # Final cleanup
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    print("Optimized GraphRAG processing completed")

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