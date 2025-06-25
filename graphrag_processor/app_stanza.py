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
from openie import StanfordOpenIE
import torch

# Configuration from environment variables
DB_URL = os.environ.get("DATABASE_URL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/app/outputs")
PROCESSING_INTERVAL = int(os.environ.get("PROCESSING_INTERVAL", "3600"))  # Default: 1 hour

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize Stanza pipeline with all required processors
print("Initializing Stanza pipeline...")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"CUDA device: {torch.cuda.get_device_name(0)}")
    print(f"CUDA memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")

stanza.download('en', verbose=False)  # Download models if not present
nlp = stanza.Pipeline('en', processors='tokenize,mwt,pos,lemma,ner,depparse,coref', verbose=False, use_gpu=torch.cuda.is_available())

# Initialize sentence transformer for entity linking
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"Initializing sentence transformer on device: {device}")
try:
    entity_linker_model = SentenceTransformer('all-MiniLM-L6-v2', device=device)
    print(f"Sentence transformer loaded successfully")
except Exception as e:
    print(f"Warning: Failed to load sentence transformer: {e}")
    print("Downloading model...")
    entity_linker_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device=device)
    print(f"Sentence transformer loaded after download")

# Initialize Stanford OpenIE for relation extraction
openie_client = None

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

# Process text with Stanza for NER and coreference resolution
def process_text_with_stanza(text):
    """
    Process text using Stanza to extract entities and resolve coreferences.
    Returns processed text and entity dictionary.
    """
    # Limit text length to avoid memory issues
    if len(text) > 10000:
        text = text[:10000]
    
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
        for repl in replacements:
            resolved_text = (
                resolved_text[:repl['start']] + 
                repl['replacement'] + 
                resolved_text[repl['end']:]
            )
    
    return resolved_text, dict(entities)

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
    doc = nlp(text)
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
    
    # Encode all entities
    embeddings = entity_linker_model.encode(entity_list, convert_to_tensor=True)
    
    # Find similar entities
    entity_mapping = {}
    for i in range(len(entity_list)):
        if entity_list[i] in entity_mapping:
            continue
            
        for j in range(i + 1, len(entity_list)):
            if entity_list[j] in entity_mapping:
                continue
                
            similarity = util.pytorch_cos_sim(embeddings[i], embeddings[j])[0][0].item()
            
            if similarity > confidence_threshold:
                # Use the shorter entity as the canonical form
                if len(entity_list[i]) <= len(entity_list[j]):
                    entity_mapping[entity_list[j]] = entity_list[i]
                else:
                    entity_mapping[entity_list[i]] = entity_list[j]
    
    # Apply entity mapping to the triple dataframe
    triple_df['subject'] = triple_df['subject'].map(lambda x: entity_mapping.get(x, x))
    triple_df['object'] = triple_df['object'].map(lambda x: entity_mapping.get(x, x))
    
    return triple_df.drop_duplicates()

# Create knowledge graph from processed data
def build_knowledge_graph(chunks_data):
    """
    Build a knowledge graph from document chunks using Stanza processing.
    """
    G = nx.Graph()
    all_triples = []
    
    for chunk_id, text, metadata, _ in chunks_data:
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
        
        # Add entities as nodes
        for entity_type, entity_list in entities.items():
            for entity in entity_list:
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
        
        # Collect triples for entity linking
        all_triples.append(relations_df)
    
    # Perform entity linking across all triples
    if all_triples:
        combined_triples = pd.concat(all_triples, ignore_index=True)
        linked_triples = link_entities(combined_triples)
        
        # Update graph with linked entities
        for _, row in linked_triples.iterrows():
            subj_id = f"ENTITY_{row['subject']}"
            obj_id = f"ENTITY_{row['object']}"
            
            if G.has_node(subj_id) and G.has_node(obj_id):
                # Increase edge weight if it already exists
                if G.has_edge(subj_id, obj_id):
                    G[subj_id][obj_id]['weight'] += 1
                else:
                    G.add_edge(subj_id, obj_id, weight=1, relation=row['relation'])
    
    return G

# Generate summaries for entity communities using LLM
def generate_entity_summaries(G, chunks_data):
    """
    Generate summaries for communities of entities in the graph.
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
        
        # Get chunk texts connected to these entities
        chunk_texts = []
        chunk_ids = set()
        for entity_node in entity_nodes:
            for neighbor in G.neighbors(entity_node):
                if G.nodes[neighbor]["type"] == "chunk":
                    chunk_id = int(neighbor.replace("chunk_", ""))
                    if chunk_id not in chunk_ids:
                        chunk_ids.add(chunk_id)
                        for c_id, text, _, _ in chunks_data:
                            if c_id == chunk_id:
                                chunk_texts.append(text)
                                break
        
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
        {context}
        
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

# Save graph and summaries to database
def save_outputs(G, summaries):
    """
    Save the knowledge graph and community summaries to database.
    """
    timestamp = datetime.now()
    
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # Clear old data if needed (optional - you might want to keep history)
            # cursor.execute("DELETE FROM graph_nodes WHERE processing_timestamp < NOW() - INTERVAL '30 days'")
            # cursor.execute("DELETE FROM graph_edges WHERE processing_timestamp < NOW() - INTERVAL '30 days'")
            # cursor.execute("DELETE FROM community_summaries WHERE processing_timestamp < NOW() - INTERVAL '30 days'")
            
            # Insert nodes
            node_count = 0
            for node, attrs in G.nodes(data=True):
                node_type = attrs.get("type", "")
                entity_type = attrs.get("entity_type", None)
                text = attrs.get("text", "")
                source = attrs.get("source", None)
                
                cursor.execute("""
                    INSERT INTO graph_nodes (node_id, node_type, entity_type, text, source, processing_timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (node_id, processing_timestamp) DO NOTHING
                """, (node, node_type, entity_type, text, source, timestamp))
                node_count += 1
            
            # Insert edges
            edge_count = 0
            for source, target, data in G.edges(data=True):
                source_type = G.nodes[source].get("type", "")
                target_type = G.nodes[target].get("type", "")
                relation = data.get('relation', None)
                weight = data.get('weight', 1.0)
                
                cursor.execute("""
                    INSERT INTO graph_edges (source_node, target_node, weight, relation, source_type, target_type, processing_timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (source, target, weight, relation, source_type, target_type, timestamp))
                edge_count += 1
            
            # Insert summaries
            summary_count = 0
            for summary in summaries:
                cursor.execute("""
                    INSERT INTO community_summaries (community_id, summary, entities, key_relations, num_entities, num_chunks, processing_timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    summary["community_id"],
                    summary["summary"],
                    json.dumps(summary["entities"]),
                    json.dumps(summary.get("key_relations", [])),
                    summary["num_entities"],
                    summary["num_chunks"],
                    timestamp
                ))
                summary_count += 1
            
            conn.commit()
    
    # Still save a reference file for backward compatibility (optional)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    latest_refs = {
        "timestamp": timestamp.strftime("%Y%m%d_%H%M%S"),
        "num_nodes": node_count,
        "num_edges": edge_count,
        "num_communities": summary_count,
        "database": "PostgreSQL"
    }
    
    with open(os.path.join(OUTPUT_DIR, "latest_refs.json"), 'w') as f:
        json.dump(latest_refs, f, indent=2)
    
    print(f"Saved graph with {node_count} nodes and {edge_count} edges to database")
    print(f"Generated {summary_count} community summaries")

# Main processing function
def process_graph():
    """
    Main function to process chunks and build knowledge graph.
    """
    print("Starting GraphRAG processing with Stanza...")
    
    # Fetch data
    chunks_data = fetch_data()
    if not chunks_data:
        print("No data to process")
        return
    
    print(f"Fetched {len(chunks_data)} document chunks")
    
    # Build graph with Stanza processing
    G = build_knowledge_graph(chunks_data)
    
    # Generate summaries
    summaries = generate_entity_summaries(G, chunks_data)
    
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