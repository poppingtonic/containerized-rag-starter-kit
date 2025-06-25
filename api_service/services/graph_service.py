import os
import json
import pandas as pd
import networkx as nx
import jsonlines
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional, Tuple
from utils import Config

class GraphService:
    def __init__(self):
        self.graph = None
        self.summaries = None
        self.refs = None
        self.db_url = Config.DB_URL
        self._load_graph_data()
    
    def _load_graph_data(self):
        """Load GraphRAG outputs from database."""
        try:
            with psycopg2.connect(self.db_url) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Check if we have any graph data
                    cursor.execute("SELECT COUNT(*) as count FROM graph_nodes")
                    if cursor.fetchone()['count'] == 0:
                        print("No GraphRAG data found in database. Using vector search only.")
                        return
                    
                    # Build graph
                    self.graph = nx.Graph()
                    
                    # Load nodes from the latest processing timestamp
                    cursor.execute("""
                        SELECT * FROM latest_graph_nodes
                    """)
                    
                    nodes = cursor.fetchall()
                    for node in nodes:
                        self.graph.add_node(node["node_id"], 
                                  type=node["node_type"], 
                                  entity_type=node["entity_type"], 
                                  text=node["text"],
                                  source=node["source"])
                    
                    # Load edges from the latest processing timestamp
                    cursor.execute("""
                        SELECT * FROM latest_graph_edges
                    """)
                    
                    edges = cursor.fetchall()
                    for edge in edges:
                        self.graph.add_edge(edge["source_node"], 
                                          edge["target_node"], 
                                          weight=edge["weight"],
                                          relation=edge["relation"])
                    
                    # Load summaries from the latest processing timestamp
                    cursor.execute("""
                        SELECT * FROM latest_community_summaries
                        ORDER BY community_id
                    """)
                    
                    self.summaries = []
                    for summary in cursor.fetchall():
                        self.summaries.append({
                            "community_id": summary["community_id"],
                            "summary": summary["summary"],
                            "entities": summary["entities"],
                            "key_relations": summary["key_relations"],
                            "num_entities": summary["num_entities"],
                            "num_chunks": summary["num_chunks"],
                            "related_chunks": []  # We'll need to compute this if needed
                        })
                    
                    # Store metadata
                    self.refs = {
                        "num_nodes": len(nodes),
                        "num_edges": len(edges),
                        "num_communities": len(self.summaries),
                        "source": "database"
                    }
                    
                    print(f"Loaded graph with {len(nodes)} nodes and {len(edges)} edges from database")
                    
        except Exception as e:
            print(f"Error loading graph data from database: {e}")
            self.graph = None
            self.summaries = None
            self.refs = None
    
    def enhance_with_graph(self, chunks: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """Enhance search results with graph data."""
        if not self.graph or not self.summaries:
            return [], []
        
        entities = []
        communities = []
        
        # Find entities mentioned in chunks
        chunk_texts = [chunk["text_content"] for chunk in chunks]
        relevant_entities = set()
        
        for node, data in self.graph.nodes(data=True):
            if data["type"] == "entity":
                entity_text = data["text"].lower()
                # Check if entity is mentioned in any chunk
                if any(entity_text in chunk_text.lower() for chunk_text in chunk_texts):
                    relevant_entities.add(node)
        
        # Calculate entity relevance
        entity_scores = {}
        for entity in relevant_entities:
            # Count connections to other relevant entities
            connections = sum(1 for neighbor in self.graph.neighbors(entity) 
                            if neighbor in relevant_entities)
            
            # Normalize by total relevant entities
            relevance = connections / len(chunks) if chunks else 0
            entity_scores[entity] = relevance
            
            entities.append({
                "entity": self.graph.nodes[entity]["text"],
                "entity_type": self.graph.nodes[entity]["entity_type"],
                "relevance": relevance
            })
        
        # Find relevant communities
        relevant_communities = set()
        for summary in self.summaries:
            # Check if any relevant entities are mentioned in this community
            if any(entity_info in summary["entities"] for entity in relevant_entities 
                  for entity_info in summary["entities"] if self.graph.nodes[entity]["text"] in entity_info):
                relevant_communities.add(summary["community_id"])
        
        # Add community information
        for summary in self.summaries:
            if summary["community_id"] in relevant_communities:
                # Calculate relevance based on entity overlap
                entity_overlap = sum(1 for entity in relevant_entities 
                                   for entity_info in summary["entities"] if self.graph.nodes[entity]["text"] in entity_info)
                
                if len(relevant_entities) > 0:
                    relevance = entity_overlap / len(relevant_entities)
                else:
                    relevance = 0.0
                
                communities.append({
                    "community_id": summary["community_id"],
                    "summary": summary["summary"],
                    "entities": summary["entities"],
                    "relevance": relevance
                })
        
        # Sort by relevance
        entities.sort(key=lambda x: x["relevance"], reverse=True)
        communities.sort(key=lambda x: x["relevance"], reverse=True)
        
        return entities, communities