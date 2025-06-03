import os
import json
import pandas as pd
import networkx as nx
import jsonlines
from typing import List, Dict, Any, Optional, Tuple
from utils import Config

class GraphService:
    def __init__(self):
        self.graph = None
        self.summaries = None
        self.refs = None
        self._load_graph_data()
    
    def _load_graph_data(self):
        """Load GraphRAG outputs."""
        try:
            # Load latest references
            refs_path = os.path.join(Config.GRAPH_OUTPUT_PATH, "latest_refs.json")
            if not os.path.exists(refs_path):
                print("No GraphRAG data found. Using vector search only.")
                return
                
            with open(refs_path, 'r') as f:
                self.refs = json.load(f)
            
            # Load edges
            edges_df = pd.read_csv(self.refs["edges"])
            
            # Load nodes
            nodes_df = pd.read_csv(self.refs["nodes"])
            
            # Load summaries
            self.summaries = []
            with jsonlines.open(self.refs["summaries"]) as reader:
                for summary in reader:
                    self.summaries.append(summary)
            
            # Build graph
            self.graph = nx.Graph()
            
            # Add nodes
            for _, row in nodes_df.iterrows():
                self.graph.add_node(row["id"], 
                          type=row["type"], 
                          entity_type=row["entity_type"], 
                          text=row["text"],
                          source=row["source"])
            
            # Add edges
            for _, row in edges_df.iterrows():
                self.graph.add_edge(row["source"], row["target"], weight=row["weight"])
                
        except Exception as e:
            print(f"Error loading graph data: {e}")
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
            # Check if any retrieved chunks are in this community
            if any(chunk_id in summary["related_chunks"] for chunk in chunks for chunk_id in [chunk["id"]]):
                relevant_communities.add(summary["community_id"])
            
            # Check if any relevant entities are mentioned in this community
            if any(entity_info in summary["entities"] for entity in relevant_entities 
                  for entity_info in summary["entities"] if self.graph.nodes[entity]["text"] in entity_info):
                relevant_communities.add(summary["community_id"])
        
        # Add community information
        for summary in self.summaries:
            if summary["community_id"] in relevant_communities:
                # Calculate relevance based on chunk and entity overlap
                chunk_overlap = sum(1 for chunk in chunks if chunk["id"] in summary["related_chunks"])
                entity_overlap = sum(1 for entity in relevant_entities 
                                   for entity_info in summary["entities"] if self.graph.nodes[entity]["text"] in entity_info)
                
                total_factors = len(chunks) + len(relevant_entities)
                if total_factors > 0:
                    relevance = (chunk_overlap + entity_overlap) / total_factors
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