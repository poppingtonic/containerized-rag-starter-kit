#!/usr/bin/env python3
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import argparse
from datetime import datetime, timedelta
import tabulate
import humanize
import sys
import time

# Default settings
DEFAULT_DB_URL = "postgresql://postgres:postgres@localhost:5433/graphrag"

def get_db_connection(db_url=None):
    """Connect to the PostgreSQL database server"""
    db_url = db_url or os.environ.get("DATABASE_URL", DEFAULT_DB_URL)
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    conn.cursor_factory = RealDictCursor
    return conn

def get_cache_stats(conn):
    """Get general statistics about the cache"""
    stats = {}
    
    with conn.cursor() as cursor:
        # Get total entries
        cursor.execute("SELECT COUNT(*) as count FROM query_cache")
        stats["total_entries"] = cursor.fetchone()["count"]
        
        # Get recently accessed entries
        cursor.execute("""
            SELECT COUNT(*) as count FROM query_cache 
            WHERE last_accessed > NOW() - INTERVAL '24 hours'
        """)
        stats["recent_entries"] = cursor.fetchone()["count"]
        
        # Get oldest and newest entries
        cursor.execute("SELECT MIN(created_at) as oldest FROM query_cache")
        stats["oldest_entry"] = cursor.fetchone()["oldest"]
        
        cursor.execute("SELECT MAX(created_at) as newest FROM query_cache")
        stats["newest_entry"] = cursor.fetchone()["newest"]
        
        # Get memory size estimation
        cursor.execute("""
            SELECT pg_size_pretty(pg_total_relation_size('query_cache')) as size
        """)
        stats["cache_size"] = cursor.fetchone()["size"]
        
        # Get entries with/without embeddings
        cursor.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE query_embedding IS NOT NULL) as with_embedding,
                COUNT(*) FILTER (WHERE query_embedding IS NULL) as without_embedding
            FROM query_cache
        """)
        embedding_stats = cursor.fetchone()
        stats["entries_with_embedding"] = embedding_stats["with_embedding"]
        stats["entries_without_embedding"] = embedding_stats["without_embedding"]
        
        # Get favorite count
        cursor.execute("""
            SELECT COUNT(*) as count FROM user_feedback WHERE is_favorite = TRUE
        """)
        stats["favorite_count"] = cursor.fetchone()["count"]
        
        # Get thread count
        cursor.execute("""
            SELECT COUNT(*) as count FROM user_feedback WHERE has_thread = TRUE
        """)
        stats["thread_count"] = cursor.fetchone()["count"]
        
    return stats

def get_recent_queries(conn, limit=10):
    """Get the most recently accessed cached queries"""
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT 
                qc.id, 
                qc.query_text, 
                qc.created_at, 
                qc.last_accessed,
                array_length(qc.chunk_ids::json, 1) as chunk_count,
                uf.is_favorite,
                uf.has_thread,
                uf.thread_title
            FROM query_cache qc
            LEFT JOIN user_feedback uf ON qc.id = uf.query_cache_id
            ORDER BY qc.last_accessed DESC
            LIMIT %s
        """, (limit,))
        return cursor.fetchall()

def get_popular_queries(conn, limit=10):
    """Get the most frequently accessed queries based on last_accessed timestamp"""
    # Note: This is an approximation since we don't store access count
    # We use the difference between created_at and last_accessed
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT 
                qc.id, 
                qc.query_text, 
                qc.created_at, 
                qc.last_accessed,
                array_length(qc.chunk_ids::json, 1) as chunk_count,
                extract(epoch from (qc.last_accessed - qc.created_at)) as age_seconds
            FROM query_cache qc
            WHERE qc.last_accessed > qc.created_at
            ORDER BY age_seconds DESC
            LIMIT %s
        """, (limit,))
        return cursor.fetchall()

def get_cache_entry(conn, entry_id):
    """Get details of a specific cache entry"""
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT 
                qc.id, 
                qc.query_text, 
                qc.answer_text, 
                qc.created_at, 
                qc.last_accessed,
                qc.references,
                qc.chunk_ids,
                qc.entities,
                qc.communities,
                uf.id as feedback_id,
                uf.rating,
                uf.feedback_text,
                uf.is_favorite,
                uf.has_thread,
                uf.thread_title
            FROM query_cache qc
            LEFT JOIN user_feedback uf ON qc.id = uf.query_cache_id
            WHERE qc.id = %s
        """, (entry_id,))
        return cursor.fetchone()

def get_time_distribution(conn, days=7):
    """Get the time distribution of cached queries"""
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT 
                date_trunc('day', created_at) as day,
                COUNT(*) as count
            FROM query_cache
            WHERE created_at > NOW() - INTERVAL %s DAY
            GROUP BY day
            ORDER BY day DESC
        """, (days,))
        return cursor.fetchall()

def clear_cache(conn, older_than=None):
    """Clear the cache, optionally only clearing entries older than specified days"""
    with conn.cursor() as cursor:
        if older_than:
            # Delete entries older than specified days
            cursor.execute("""
                DELETE FROM query_cache
                WHERE created_at < NOW() - INTERVAL %s DAY
                RETURNING id
            """, (older_than,))
            deleted = cursor.fetchall()
            deleted_count = len(deleted)
            conn.commit()
            return f"Deleted {deleted_count} cache entries older than {older_than} days"
        else:
            # Clear entire cache
            cursor.execute("TRUNCATE TABLE query_cache CASCADE")
            conn.commit()
            return "Cache cleared completely"

def format_time_ago(dt):
    """Format a datetime as a human-readable time ago string"""
    if not dt:
        return "never"
    
    now = datetime.now(dt.tzinfo)
    return humanize.naturaltime(now - dt)

def print_cache_stats(stats):
    """Pretty print cache statistics"""
    print("\n=== CACHE STATISTICS ===")
    print(f"Total entries: {stats['total_entries']}")
    print(f"Entries accessed in last 24h: {stats['recent_entries']}")
    print(f"Oldest entry: {stats['oldest_entry']} ({format_time_ago(stats['oldest_entry'])})")
    print(f"Newest entry: {stats['newest_entry']} ({format_time_ago(stats['newest_entry'])})")
    print(f"Cache size: {stats['cache_size']}")
    print(f"Entries with embedding: {stats['entries_with_embedding']}")
    print(f"Entries without embedding: {stats['entries_without_embedding']}")
    print(f"Favorites: {stats['favorite_count']}")
    print(f"Threads: {stats['thread_count']}")

def print_recent_queries(queries):
    """Pretty print recent queries"""
    if not queries:
        print("\nNo recent queries found")
        return
        
    print("\n=== RECENT QUERIES ===")
    table_data = []
    headers = ["ID", "Query", "Created", "Last Accessed", "Chunks", "Favorite", "Thread"]
    
    for q in queries:
        # Truncate query text for display
        query_text = q["query_text"]
        if len(query_text) > 60:
            query_text = query_text[:57] + "..."
            
        table_data.append([
            q["id"],
            query_text,
            format_time_ago(q["created_at"]),
            format_time_ago(q["last_accessed"]),
            q["chunk_count"] or 0,
            "✓" if q["is_favorite"] else "",
            q["thread_title"] if q["has_thread"] else ""
        ])
    
    print(tabulate.tabulate(table_data, headers=headers, tablefmt="grid"))

def print_popular_queries(queries):
    """Pretty print popular queries"""
    if not queries:
        print("\nNo popular queries found")
        return
        
    print("\n=== POPULAR QUERIES ===")
    table_data = []
    headers = ["ID", "Query", "Created", "Last Accessed", "Chunks", "Age"]
    
    for q in queries:
        # Truncate query text for display
        query_text = q["query_text"]
        if len(query_text) > 60:
            query_text = query_text[:57] + "..."
            
        # Format age
        age_seconds = q["age_seconds"]
        if age_seconds:
            age = humanize.naturaldelta(timedelta(seconds=age_seconds))
        else:
            age = "New"
            
        table_data.append([
            q["id"],
            query_text,
            format_time_ago(q["created_at"]),
            format_time_ago(q["last_accessed"]),
            q["chunk_count"] or 0,
            age
        ])
    
    print(tabulate.tabulate(table_data, headers=headers, tablefmt="grid"))

def print_time_distribution(distribution):
    """Pretty print time distribution"""
    if not distribution:
        print("\nNo time distribution data available")
        return
        
    print("\n=== QUERY DISTRIBUTION (LAST 7 DAYS) ===")
    table_data = []
    headers = ["Date", "Count"]
    
    for d in distribution:
        day_str = d["day"].strftime("%Y-%m-%d") if d["day"] else "Unknown"
        table_data.append([day_str, d["count"]])
    
    print(tabulate.tabulate(table_data, headers=headers, tablefmt="grid"))

def print_cache_entry(entry):
    """Pretty print details of a cache entry"""
    if not entry:
        print("\nEntry not found")
        return
        
    print(f"\n=== CACHE ENTRY {entry['id']} ===")
    print(f"Query: {entry['query_text']}")
    print(f"Created: {entry['created_at']} ({format_time_ago(entry['created_at'])})")
    print(f"Last accessed: {entry['last_accessed']} ({format_time_ago(entry['last_accessed'])})")
    
    # User feedback
    if entry["feedback_id"]:
        print("\n--- USER FEEDBACK ---")
        print(f"Rating: {entry['rating']} stars") if entry["rating"] else print("Rating: None")
        print(f"Feedback: {entry['feedback_text']}") if entry["feedback_text"] else print("Feedback: None")
        print(f"Favorite: {'Yes' if entry['is_favorite'] else 'No'}")
        if entry["has_thread"]:
            print(f"Thread: Yes ('{entry['thread_title']}')")
        else:
            print("Thread: No")
    
    # References
    if entry["references"]:
        print("\n--- REFERENCES ---")
        references = json.loads(entry["references"]) if isinstance(entry["references"], str) else entry["references"]
        for i, ref in enumerate(references, 1):
            print(f"[{i}] {ref}")
    
    # Answer text
    print("\n--- ANSWER ---")
    print(entry["answer_text"])

def main():
    parser = argparse.ArgumentParser(description="Check and manage the GraphRAG query cache")
    parser.add_argument("--db-url", help="Database connection URL")
    parser.add_argument("--stats", action="store_true", help="Show cache statistics")
    parser.add_argument("--recent", type=int, nargs="?", const=10, help="Show recent queries (default: 10)")
    parser.add_argument("--popular", type=int, nargs="?", const=10, help="Show popular queries (default: 10)")
    parser.add_argument("--distribution", type=int, nargs="?", const=7, help="Show time distribution (default: 7 days)")
    parser.add_argument("--entry", type=int, help="Show details for a specific cache entry")
    parser.add_argument("--clear", action="store_true", help="Clear the entire cache")
    parser.add_argument("--clear-older-than", type=int, help="Clear cache entries older than specified days")
    parser.add_argument("--monitor", action="store_true", help="Monitor cache in real-time (refresh every 5 seconds)")
    
    args = parser.parse_args()
    
    # Default action if no arguments provided
    if len(sys.argv) == 1:
        args.stats = True
        args.recent = 10
    
    try:
        conn = get_db_connection(args.db_url)
        
        if args.clear:
            result = clear_cache(conn)
            print(result)
            return
            
        if args.clear_older_than:
            result = clear_cache(conn, args.clear_older_than)
            print(result)
            return
            
        if args.entry:
            entry = get_cache_entry(conn, args.entry)
            print_cache_entry(entry)
            return
        
        if args.monitor:
            try:
                while True:
                    os.system('clear' if os.name == 'posix' else 'cls')
                    stats = get_cache_stats(conn)
                    recent = get_recent_queries(conn, 5)
                    distribution = get_time_distribution(conn, 7)
                    
                    print(f"CACHE MONITOR - Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    print_cache_stats(stats)
                    print_recent_queries(recent)
                    print_time_distribution(distribution)
                    print("\nPress Ctrl+C to exit...")
                    time.sleep(5)
            except KeyboardInterrupt:
                print("\nExiting monitor mode...")
                return
        
        # Normal one-time reports
        if args.stats:
            stats = get_cache_stats(conn)
            print_cache_stats(stats)
            
        if args.recent:
            recent = get_recent_queries(conn, args.recent)
            print_recent_queries(recent)
            
        if args.popular:
            popular = get_popular_queries(conn, args.popular)
            print_popular_queries(popular)
            
        if args.distribution:
            distribution = get_time_distribution(conn, args.distribution)
            print_time_distribution(distribution)
            
    except Exception as e:
        print(f"Error: {e}")
        if "connection" in str(e).lower():
            print("\nDatabase connection error. Make sure the database is running.")
            print(f"Using connection string: {args.db_url or DEFAULT_DB_URL}")
        return 1
    finally:
        if 'conn' in locals():
            conn.close()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())