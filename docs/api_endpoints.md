# API Endpoints Documentation

## Base URL
All endpoints are served at: `http://localhost:8000`

## Core Query Endpoints

### POST /query
Process a user query and return comprehensive results.

**Request Body:**
```json
{
  "query": "string",
  "max_results": 5,
  "use_memory": true
}
```

**Response:**
```json
{
  "query": "string",
  "answer": "string",
  "chunks": [...],
  "entities": [...],
  "communities": [...],
  "references": [...],
  "from_memory": false,
  "memory_id": 123
}
```

## Cache Management Endpoints

### GET /cache/entries
Get all cache entries with optional feedback data.

**Query Parameters:**
- `limit` (int, default: 50): Number of entries to return
- `offset` (int, default: 0): Pagination offset
- `include_feedback` (bool, default: true): Include feedback data

**Response:**
```json
{
  "status": "success",
  "total": 100,
  "limit": 50,
  "offset": 0,
  "entries": [
    {
      "id": 1,
      "query": "string",
      "answer": "string",
      "references": [...],
      "chunks": [...],
      "created_at": "2024-01-01T00:00:00",
      "access_count": 5,
      "last_accessed": "2024-01-02T00:00:00",
      "feedback": {
        "text": "string",
        "rating": 5,
        "is_favorite": true,
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-02T00:00:00"
      }
    }
  ]
}
```

## Evaluation Endpoints

### GET /evaluation/metrics
Get aggregated evaluation metrics from user feedback.

**Response:**
```json
{
  "status": "success",
  "metrics": {
    "overall": {
      "total_feedback": 100,
      "rated_count": 80,
      "average_rating": 4.2,
      "favorites_count": 25,
      "text_feedback_count": 45
    },
    "rating_distribution": [
      {"rating": 5, "count": 30},
      {"rating": 4, "count": 25},
      {"rating": 3, "count": 15},
      {"rating": 2, "count": 7},
      {"rating": 1, "count": 3}
    ],
    "timeline": [
      {
        "date": "2024-01-01",
        "feedback_count": 10,
        "average_rating": 4.5
      }
    ]
  }
}
```

## Export Endpoints

### GET /export/training-data
Export cache entries with feedback for training purposes.

**Query Parameters:**
- `format` (string, default: "jsonl"): Export format - jsonl, csv, or json
- `min_rating` (int, optional): Minimum rating to include
- `only_favorites` (bool, default: false): Only export favorites
- `include_chunks` (bool, default: true): Include retrieved chunks

**Response:**
- For `format=jsonl`: Returns JSONL file download
- For `format=csv`: Returns CSV file download
- For `format=json`: Returns JSON response with data array

### GET /export/evaluation-report
Generate a comprehensive evaluation report.

**Response:**
```json
{
  "status": "success",
  "report": {
    "summary": {
      "total_evaluated": 80,
      "average_rating": 4.2,
      "rating_distribution": {...},
      "favorites_count": 25,
      "feedback_provided": 45
    },
    "rating_analysis": {
      "5": {
        "count": 30,
        "avg_answer_length": 250,
        "avg_references": 3.5,
        "avg_chunks": 4.2,
        "favorites_percentage": 60
      }
    },
    "feedback_samples": {
      "5": ["Great answer!", "Very helpful", "Exactly what I needed"]
    },
    "recommendations": [
      "Higher-rated answers tend to use more chunks. Consider retrieving more context."
    ]
  },
  "generated_at": "2024-01-01 12:00:00"
}
```

## Memory Management Endpoints

### GET /memory/stats
Get memory usage statistics.

**Response:**
```json
{
  "status": "success",
  "total_entries": 500,
  "total_accesses": 2500,
  "average_accesses": 5.0,
  "max_accesses": 50,
  "oldest_entry": "2024-01-01T00:00:00",
  "newest_entry": "2024-01-15T00:00:00",
  "most_accessed": [...],
  "recent_queries": [...]
}
```

### DELETE /memory/clear
Clear all remembered queries.

**Response:**
```json
{
  "status": "success",
  "message": "Cleared 500 memory entries",
  "deleted_entries": 500,
  "timestamp": "2024-01-15 12:00:00"
}
```

### GET /memory/entry/{entry_id}
Get a specific memory entry.

**Response:**
```json
{
  "status": "success",
  "entry": {
    "id": 123,
    "query": "string",
    "answer": "string",
    "references": [...],
    "chunks": [...],
    "entities": [...],
    "communities": [...],
    "created_at": "2024-01-01T00:00:00",
    "access_count": 5,
    "last_accessed": "2024-01-02T00:00:00"
  }
}
```

### DELETE /memory/entry/{entry_id}
Delete a specific remembered query.

**Response:**
```json
{
  "status": "success",
  "message": "Memory entry 123 deleted successfully",
  "timestamp": "2024-01-15 12:00:00"
}
```

## Feedback Endpoints

### POST /feedback
Save user feedback for a query.

**Request Body:**
```json
{
  "memory_id": 123,
  "feedback_text": "Great answer!",
  "rating": 5,
  "is_favorite": true
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Feedback saved successfully",
  "id": 456
}
```

### GET /favorites
Get all favorite queries.

**Response:**
```json
{
  "status": "success",
  "favorites": [
    {
      "id": 123,
      "query": "string",
      "answer": "string",
      "references": [...],
      "created_at": "2024-01-01T00:00:00",
      "rating": 5,
      "feedback": "Great answer!",
      "favorited_at": "2024-01-02T00:00:00"
    }
  ]
}
```

## Thread Management Endpoints

### POST /thread/create
Create a new conversation thread from a favorite query.

**Request Body:**
```json
{
  "memory_id": 123,
  "thread_title": "Discussion about X"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Thread created successfully",
  "thread_id": 789,
  "memory_id": 123,
  "title": "Discussion about X"
}
```

### GET /threads
Get all conversation threads.

**Response:**
```json
{
  "status": "success",
  "threads": [
    {
      "id": 789,
      "title": "Discussion about X",
      "memory_id": 123,
      "original_query": "string",
      "message_count": 5,
      "created_at": "2024-01-01T00:00:00"
    }
  ]
}
```

### GET /thread/{thread_id}
Get a specific thread with all messages.

**Response:**
```json
{
  "id": 789,
  "title": "Discussion about X",
  "memory_id": 123,
  "original_query": "string",
  "original_answer": "string",
  "messages": [
    {
      "id": 1,
      "message": "string",
      "is_user": true,
      "references": [...],
      "chunks": [...],
      "created_at": "2024-01-01T00:00:00"
    }
  ],
  "created_at": "2024-01-01T00:00:00"
}
```

### POST /thread/message
Add a new message to a thread.

**Request Body:**
```json
{
  "feedback_id": 789,
  "message": "Can you explain more about X?",
  "enhance_with_retrieval": true,
  "max_results": 3
}
```

**Response:**
```json
{
  "status": "success",
  "user_message_id": 10,
  "assistant_message_id": 11,
  "response": "string",
  "references": [...],
  "chunks": [...]
}
```

## Health & Status Endpoints

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15 12:00:00",
  "services": {
    "database": "connected",
    "api": "running"
  }
}
```

### GET /ingestion/progress
Get the current ingestion progress.

**Response:**
```json
{
  "status": "processing",
  "files_processed": 45,
  "total_files": 100,
  "current_file": "document.pdf",
  "chunks_created": 1250
}
```

### POST /ingestion/trigger
Manually trigger document ingestion.

**Response:**
```json
{
  "status": "success",
  "message": "Ingestion triggered successfully"
}
```

## Error Responses

All endpoints may return error responses in the following format:

```json
{
  "status": "error",
  "message": "Error description",
  "detail": "Additional error details (optional)"
}
```

Common HTTP status codes:
- 200: Success
- 400: Bad Request
- 404: Not Found
- 500: Internal Server Error
- 503: Service Unavailable