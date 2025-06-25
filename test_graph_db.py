#!/usr/bin/env python3
"""
Test script to verify graph database tables are created and functioning correctly.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Database connection string
DB_URL = os.environ.get("DATABASE_URL", "postgresql://graphraguser:graphragpassword@localhost:5433/graphragdb")

def test_database_tables():
    """Test that the graph tables exist and can be written to."""
    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                print("Testing database connection...")
                
                # Check if tables exist
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('graph_nodes', 'graph_edges', 'community_summaries')
                    ORDER BY table_name
                """)
                
                tables = [row['table_name'] for row in cursor.fetchall()]
                print(f"\nFound tables: {tables}")
                
                if len(tables) < 3:
                    print("ERROR: Not all required tables exist!")
                    return False
                
                # Test inserting sample data
                timestamp = datetime.now()
                
                # Insert a test node
                cursor.execute("""
                    INSERT INTO graph_nodes (node_id, node_type, entity_type, text, processing_timestamp)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, ("test_entity_1", "entity", "PERSON", "Test Person", timestamp))
                
                node_id = cursor.fetchone()['id']
                print(f"\nSuccessfully inserted test node with id: {node_id}")
                
                # Insert another test node
                cursor.execute("""
                    INSERT INTO graph_nodes (node_id, node_type, entity_type, text, processing_timestamp)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, ("test_entity_2", "entity", "ORGANIZATION", "Test Org", timestamp))
                
                # Insert a test edge
                cursor.execute("""
                    INSERT INTO graph_edges (source_node, target_node, weight, relation, source_type, target_type, processing_timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, ("test_entity_1", "test_entity_2", 1.0, "works_for", "entity", "entity", timestamp))
                
                edge_id = cursor.fetchone()['id']
                print(f"Successfully inserted test edge with id: {edge_id}")
                
                # Insert a test community summary
                cursor.execute("""
                    INSERT INTO community_summaries (community_id, summary, entities, key_relations, num_entities, num_chunks, processing_timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (1, "Test community summary", '["Test Person (PERSON)", "Test Org (ORGANIZATION)"]', 
                      '["Test Person - works_for - Test Org"]', 2, 1, timestamp))
                
                summary_id = cursor.fetchone()['id']
                print(f"Successfully inserted test community summary with id: {summary_id}")
                
                # Test views
                cursor.execute("SELECT COUNT(*) as count FROM latest_graph_nodes")
                node_count = cursor.fetchone()['count']
                print(f"\nView 'latest_graph_nodes' has {node_count} rows")
                
                cursor.execute("SELECT COUNT(*) as count FROM latest_graph_edges")
                edge_count = cursor.fetchone()['count']
                print(f"View 'latest_graph_edges' has {edge_count} rows")
                
                cursor.execute("SELECT COUNT(*) as count FROM latest_community_summaries")
                summary_count = cursor.fetchone()['count']
                print(f"View 'latest_community_summaries' has {summary_count} rows")
                
                # Clean up test data
                cursor.execute("DELETE FROM graph_nodes WHERE node_id LIKE 'test_%'")
                cursor.execute("DELETE FROM community_summaries WHERE summary = 'Test community summary'")
                conn.commit()
                
                print("\nAll tests passed! Database tables are working correctly.")
                return True
                
    except Exception as e:
        print(f"\nERROR: {e}")
        return False

if __name__ == "__main__":
    print("GraphRAG Database Table Test")
    print("=" * 40)
    success = test_database_tables()
    exit(0 if success else 1)