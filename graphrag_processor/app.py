import os
import json
import time
import psycopg2
import stanza
import pandas as pd
from openai import OpenAI
from datetime import datetime
from collections import defaultdict
from sentence_transformers import SentenceTransformer, util
from stanford_openie import StanfordOpenIE
import torch
import gc
import csv
from psycopg2.extras import RealDictCursor

# Configuration from environment variables
DB_URL = os.environ.get("DATABASE_URL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/app/outputs")
PROCESSING_INTERVAL = int(os.environ.get("PROCESSING_INTERVAL", "3600"))  # Default: 1 hour
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "50"))  # Process chunks in batches
MAX_TEXT_LENGTH = int(os.environ.get("MAX_TEXT_LENGTH", "5000"))  # Limit text length for processing
ENABLE_COREFERENCE = os.environ.get("ENABLE_COREFERENCE", "true").lower() == "true"
ENABLE_OPENIE = os.environ.get("ENABLE_OPENIE", "true").lower() == "true"

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize Stanza pipeline with all required processors
print("Initializing Stanza pipeline...")
stanza.download('en', verbose=False)  # Download models if not present

# Choose processors based on configuration
if ENABLE_COREFERENCE:
    processors = 'tokenize,mwt,pos,lemma,ner,depparse,coref'
else:
    processors = 'tokenize,mwt,pos,lemma,ner,depparse'

nlp = stanza.Pipeline('en', processors=processors, verbose=False, use_gpu=torch.cuda.is_available())

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
                    dc.source_metadata
                FROM 
                    document_chunks dc
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
        if ENABLE_COREFERENCE and hasattr(doc, 'coref_chains') and doc.coref_chains:
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
        
        return resolved_text, dict(entities), doc
    except Exception as e:
        print(f"Error processing text with Stanza: {e}")
        return text, {}, None

# Extract relations using Stanford OpenIE
def extract_relations_openie(text):
    """
    Extract relations from text using Stanford OpenIE.
    Returns a list of triples.
    """
    global openie_client
    
    if not ENABLE_OPENIE:
        return []
    
    if openie_client is None:
        try:
            openie_client = StanfordOpenIE()
        except Exception as e:
            print(f"Failed to initialize OpenIE: {e}")
            return []
    
    try:
        triples = []
        for triple in openie_client.annotate(text[:MAX_TEXT_LENGTH]):
            triples.append({
                'subject': triple['subject'],
                'relation': triple['relation'],
                'object': triple['object']
            })
        return triples
    except Exception as e:
        print(f"Error extracting relations: {e}")
        return []

# Extract relations using Stanza dependency parsing
def extract_relations_stanza(doc, entities):
    """
    Extract relations from text using Stanza's dependency parsing.
    This is a more sophisticated approach that uses grammatical patterns.
    """
    if doc is None:
        return []
        
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
        
        # Also look for compound patterns (e.g., "CEO of Company")
        for word in sent.words:
            if word.deprel == 'nmod' and word.upos in ['NOUN', 'PROPN']:
                head_word = sent.words[word.head - 1]
                if head_word.upos in ['NOUN', 'PROPN']:
                    # Find the preposition
                    prep = None
                    for child in sent.words:
                        if child.head == word.id and child.deprel == 'case':
                            prep = child.text
                            break
                    
                    if prep:
                        triples.append({
                            'subject': head_word.text,
                            'relation': prep,
                            'object': word.text
                        })
    
    return triples

# Entity linking using sentence transformers
def link_entities_batch(triples_batch, confidence_threshold=0.85):
    """
    Link similar entities in a batch of triples using sentence transformers.
    """
    if not triples_batch:
        return triples_batch
    
    # Get all unique entities
    all_entities = set()
    for triple in triples_batch:
        all_entities.add(triple['subject'])
        all_entities.add(triple['object'])
    
    entity_list = list(all_entities)
    
    if len(entity_list) < 2:
        return triples_batch
    
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
    
    # Apply entity mapping to triples
    linked_triples = []
    for triple in triples_batch:
        linked_triples.append({
            'subject': entity_mapping.get(triple['subject'], triple['subject']),
            'relation': triple['relation'],
            'object': entity_mapping.get(triple['object'], triple['object'])
        })
    
    return linked_triples

# Process chunks and stream triples to files
def process_chunks_streaming():
    """
    Process chunks and immediately write triples to files without building graph in memory.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Output files
    triples_csv = os.path.join(OUTPUT_DIR, f"triples_{timestamp}.csv")
    triples_ttl = os.path.join(OUTPUT_DIR, f"triples_{timestamp}.ttl")
    entities_csv = os.path.join(OUTPUT_DIR, f"entities_{timestamp}.csv")
    stats_json = os.path.join(OUTPUT_DIR, f"stats_{timestamp}.json")
    
    # Statistics counters
    stats = {
        'total_chunks': 0,
        'total_triples': 0,
        'total_entities': 0,
        'entity_types': defaultdict(int),
        'relation_types': defaultdict(int),
        'processing_config': {
            'coreference_enabled': ENABLE_COREFERENCE,
            'openie_enabled': ENABLE_OPENIE,
            'batch_size': BATCH_SIZE,
            'max_text_length': MAX_TEXT_LENGTH
        }
    }
    
    # Open output files
    with open(triples_csv, 'w', newline='', encoding='utf-8') as csv_file, \
         open(triples_ttl, 'w', encoding='utf-8') as ttl_file, \
         open(entities_csv, 'w', newline='', encoding='utf-8') as ent_file:
        
        # CSV writers
        triple_writer = csv.DictWriter(csv_file, fieldnames=['chunk_id', 'subject', 'relation', 'object', 'source'])
        triple_writer.writeheader()
        
        entity_writer = csv.DictWriter(ent_file, fieldnames=['chunk_id', 'entity', 'entity_type', 'source'])
        entity_writer.writeheader()
        
        # TTL header
        ttl_file.write("@prefix : <http://example.org/> .\n")
        ttl_file.write("@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n\n")
        
        # Get total chunks
        total_chunks = get_chunk_count()
        print(f"Total chunks to process: {total_chunks}")
        
        # Process in batches
        for offset in range(0, total_chunks, BATCH_SIZE):
            batch_num = offset // BATCH_SIZE + 1
            print(f"Processing batch {batch_num} of {(total_chunks + BATCH_SIZE - 1) // BATCH_SIZE}")
            
            # Fetch batch
            chunks_batch = fetch_data_batch(offset, BATCH_SIZE)
            batch_triples = []  # Collect triples for entity linking
            
            for chunk_id, text, metadata in chunks_batch:
                stats['total_chunks'] += 1
                metadata_dict = json.loads(metadata) if isinstance(metadata, str) else metadata
                source = metadata_dict.get("source", "unknown")
                
                # Process text with Stanza
                resolved_text, entities, doc = process_text_with_stanza(text)
                
                # Write entities to CSV
                for entity_type, entity_list in entities.items():
                    stats['entity_types'][entity_type] += len(entity_list)
                    stats['total_entities'] += len(entity_list)
                    
                    for entity in entity_list:
                        entity_writer.writerow({
                            'chunk_id': chunk_id,
                            'entity': entity,
                            'entity_type': entity_type,
                            'source': source
                        })
                
                # Extract relations (try OpenIE first, fallback to Stanza)
                relations = []
                if ENABLE_OPENIE:
                    relations = extract_relations_openie(resolved_text)
                
                if not relations and doc is not None:
                    relations = extract_relations_stanza(doc, entities)
                
                # Add chunk info to relations
                for rel in relations:
                    rel['chunk_id'] = chunk_id
                    rel['source'] = source
                    batch_triples.append(rel)
            
            # Link entities in the batch
            linked_triples = link_entities_batch(batch_triples)
            
            # Write linked triples to files
            for triple in linked_triples:
                stats['total_triples'] += 1
                stats['relation_types'][triple['relation']] += 1
                
                # Write to CSV
                triple_writer.writerow({
                    'chunk_id': triple['chunk_id'],
                    'subject': triple['subject'],
                    'relation': triple['relation'],
                    'object': triple['object'],
                    'source': triple['source']
                })
                
                # Write to TTL
                # Clean entities for TTL format
                subj_clean = triple['subject'].replace(' ', '_').replace('"', '').replace('\n', '_')
                obj_clean = triple['object'].replace(' ', '_').replace('"', '').replace('\n', '_')
                rel_clean = triple['relation'].replace(' ', '_').replace('"', '').replace('\n', '_')
                
                ttl_file.write(f":{subj_clean} :{rel_clean} :{obj_clean} .\n")
                
                # Also save to database
                save_triple_to_db(triple['chunk_id'], triple['subject'], triple['relation'], triple['object'])
            
            # Force garbage collection after each batch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            # Flush files
            csv_file.flush()
            ttl_file.flush()
            ent_file.flush()
            
            print(f"Batch {batch_num} complete. Triples so far: {stats['total_triples']}")
    
    # Save statistics
    with open(stats_json, 'w') as f:
        json.dump({
            **stats,
            'entity_types': dict(stats['entity_types']),
            'relation_types': dict(stats['relation_types']),
            'timestamp': timestamp,
            'files': {
                'triples_csv': os.path.basename(triples_csv),
                'triples_ttl': os.path.basename(triples_ttl),
                'entities_csv': os.path.basename(entities_csv)
            }
        }, f, indent=2)
    
    # Create latest reference
    with open(os.path.join(OUTPUT_DIR, "latest_refs.json"), 'w') as f:
        json.dump({
            'timestamp': timestamp,
            'triples_csv': triples_csv,
            'triples_ttl': triples_ttl,
            'entities_csv': entities_csv,
            'stats': stats_json,
            'total_triples': stats['total_triples'],
            'total_entities': stats['total_entities'],
            'total_chunks': stats['total_chunks']
        }, f, indent=2)
    
    print(f"Processing complete. Exported {stats['total_triples']} triples and {stats['total_entities']} entities")

# Save single triple to database
def save_triple_to_db(chunk_id, subject, relation, obj):
    """Save a single triple to database."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO entity_triples (chunk_id, subject, relation, object)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (chunk_id, subject, relation, obj))
                conn.commit()
    except Exception as e:
        print(f"Error saving triple to database: {e}")

# Create database tables and views
def create_database_schema():
    """Create necessary database tables and views."""
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
            
            # Create view
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
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_entity_triples_chunk_id 
                ON entity_triples(chunk_id);
            """)
            
            conn.commit()
            print("Created entity_triples table and view")

# Main processing function
def process_graph():
    """
    Main function to process chunks and export triples.
    """
    print("Starting optimized GraphRAG processing...")
    print(f"Configuration: Coreference={ENABLE_COREFERENCE}, OpenIE={ENABLE_OPENIE}, Batch={BATCH_SIZE}")
    
    # Create database schema if needed
    create_database_schema()
    
    # Check if there's data to process
    total_chunks = get_chunk_count()
    if total_chunks == 0:
        print("No data to process")
        return
    
    # Process chunks with streaming export
    process_chunks_streaming()
    
    # Final cleanup
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
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