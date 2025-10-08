# Smart Document Ingestion Guide

This guide explains how to use the intelligent document ingestion system that automatically processes and routes documents to appropriate knowledge stores.

## Overview

The smart ingestion system provides:

1. **Multi-format Support**: Process 50+ document types via unstructured-api
2. **Automatic Routing**: Documents routed to stores based on type, content, and metadata
3. **Store Auto-Creation**: Creates stores automatically as needed
4. **Deduplication**: Prevents processing the same document twice
5. **Metadata Extraction**: Extracts structure (titles, tables, etc.) from documents

## Supported Document Types

Via unstructured-api, the system supports:

**Documents**:
- PDF (including scanned PDFs with OCR)
- Microsoft Word (.doc, .docx)
- Text files (.txt, .rtf)
- Markdown (.md)
- OpenDocument (.odt)

**Presentations**:
- PowerPoint (.ppt, .pptx)
- Keynote (.key)
- OpenDocument Presentation (.odp)

**Spreadsheets**:
- Excel (.xls, .xlsx)
- CSV files
- OpenDocument Spreadsheet (.ods)

**Images** (with OCR):
- JPEG, PNG, TIFF, BMP, GIF
- Scanned documents as images

**Email**:
- Email files (.eml, .msg)
- Email threads

**Web/Data**:
- HTML files
- XML files
- JSON files

**And many more...**

## Quick Start

### 1. Start Services

```bash
docker-compose up -d
```

This starts:
- `unstructured-api` on port 8001
- `knowledge-system` service on port 8100
- Database and other services

### 2. Ingest a Document

```bash
curl -X POST http://localhost:8100/ingest/file \
  -H "Content-Type: application/json" \
  -d '{
    "filepath": "/path/to/document.pdf",
    "strategy": "auto"
  }'
```

Response:
```json
{
  "success": true,
  "filename": "document.pdf",
  "store_id": "pdf_documents",
  "doc_id": "pdf_documents_a1b2c3d4e5f6",
  "routing_info": {
    "rule_id": "pdf_rule",
    "rule_name": "General PDFs",
    "confidence": 1.0
  },
  "processing_time_seconds": 2.45
}
```

### 3. Query the Ingested Document

```bash
curl -X POST http://localhost:8100/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is this document about?",
    "workflow_id": "demo_workflow",
    "user_id": "alice@company.com",
    "user_email": "alice@company.com",
    "user_roles": ["employee"]
  }'
```

## How Routing Works

### Routing Strategies

Documents can be routed using several strategies:

1. **File Extension**
   ```yaml
   strategy: file_extension
   file_extensions:
     - pdf
     - docx
   target_store_id: documents
   ```

2. **Metadata Field**
   ```yaml
   strategy: metadata_field
   metadata_field: classification
   metadata_values:
     - confidential
     - secret
   target_store_id: confidential
   ```

3. **Content Pattern** (regex)
   ```yaml
   strategy: content_pattern
   content_patterns:
     - "(?i)contract"
     - "(?i)agreement"
   target_store_id: legal
   ```

4. **Custom Function**
   ```yaml
   strategy: custom_function
   custom_function: is_meeting_document
   target_store_id: meetings
   ```

### Priority System

Rules are evaluated in priority order (lower number = higher priority):

```yaml
routing_rules:
  - rule_id: confidential_rule
    priority: 5  # Checked first
    ...

  - rule_id: meetings_rule
    priority: 10  # Checked second
    ...

  - rule_id: general_pdf_rule
    priority: 80  # Checked near end
    ...
```

### Example Routing Rules

The system comes with 15+ pre-configured rules. Here are some examples:

**Meeting Documents**:
```yaml
- rule_id: meetings_rule
  name: "Meeting Documents"
  strategy: custom_function
  custom_function: is_meeting_document
  target_store_id: meetings
  priority: 10
```

Detects meetings based on:
- Filenames containing: "meeting", "minutes", "standup", "sync"
- Metadata type: "meeting" or "transcript"
- Content patterns: "agenda:", "attendees:", "action items:"

**Confidential Documents**:
```yaml
- rule_id: confidential_metadata_rule
  name: "Confidential by Metadata"
  strategy: metadata_field
  metadata_field: classification
  metadata_values:
    - confidential
    - secret
    - restricted
  target_store_id: confidential
  priority: 5  # High priority - check first
```

**Legal Documents**:
```yaml
- rule_id: legal_docs_rule
  name: "Legal Documents"
  strategy: content_pattern
  content_patterns:
    - "(?i)contract"
    - "(?i)agreement"
    - "(?i)terms and conditions"
  target_store_id: legal
  priority: 15
```

## API Reference

### POST /ingest/file

Ingest a single file with automatic routing.

**Request**:
```json
{
  "filepath": "/path/to/document.pdf",
  "metadata": {
    "title": "Q4 Planning",
    "author": "alice@company.com",
    "classification": "confidential",
    "tags": ["planning", "q4"]
  },
  "strategy": "hi_res",
  "force_store_id": "specific_store"
}
```

**Parameters**:
- `filepath` (required): Path to file to ingest
- `metadata` (optional): Additional metadata for the document
- `strategy` (optional): Processing strategy
  - `auto`: Automatically choose best strategy (default)
  - `fast`: Fast processing, may miss details
  - `hi_res`: High-resolution processing, more detailed
  - `ocr_only`: Only use OCR for scanned documents
- `force_store_id` (optional): Force routing to specific store (bypasses rules)

**Response**:
```json
{
  "success": true,
  "filename": "document.pdf",
  "store_id": "confidential",
  "doc_id": "confidential_a1b2c3d4e5f6",
  "routing_info": {
    "rule_id": "confidential_metadata_rule",
    "rule_name": "Confidential by Metadata",
    "confidence": 1.0
  },
  "processing_time_seconds": 3.21
}
```

### GET /ingest/statistics

Get ingestion statistics and routing information.

**Request**:
```bash
curl http://localhost:8100/ingest/statistics
```

**Response**:
```json
{
  "total_processed_files": 42,
  "routing_statistics": {
    "total_rules": 15,
    "enabled_rules": 15,
    "rules_by_strategy": {
      "file_extension": 5,
      "metadata_field": 3,
      "content_pattern": 4,
      "custom_function": 3
    },
    "rules_by_store": {
      "meetings": 1,
      "emails": 1,
      "confidential": 2,
      "legal": 1,
      "pdf_documents": 1
    }
  },
  "unstructured_api_healthy": true
}
```

### GET /ingest/routing-rules

View active routing rules.

**Request**:
```bash
curl http://localhost:8100/ingest/routing-rules
```

**Response**:
```json
{
  "rules": [
    {
      "rule_id": "confidential_metadata_rule",
      "name": "Confidential by Metadata",
      "description": "Route documents marked as confidential",
      "strategy": "metadata_field",
      "target_store_id": "confidential",
      "priority": 5,
      "enabled": true
    },
    ...
  ]
}
```

## Advanced Usage

### Custom Routing Rules

You can define custom routing rules in `routing_rules.yaml`:

```yaml
routing_rules:
  - rule_id: my_custom_rule
    name: "Custom Rule"
    description: "Route based on custom criteria"
    strategy: file_extension
    file_extensions:
      - custom
    target_store_id: my_store
    priority: 50
    enabled: true
```

### Store Configurations

Define how auto-created stores should be configured:

```yaml
store_configs:
  my_store:
    description: "My custom store"
    pii_level: partial
    audit_level: detailed
    requires_roles:
      - employee
    auto_create: true
```

### Custom Detection Functions

Add custom detection logic:

```python
from knowledge_system.ingestion import DocumentRouter

def is_financial_report(filename, content, metadata):
    """Detect financial reports"""
    keywords = ['revenue', 'expenses', 'profit', 'loss']
    if content:
        return sum(1 for k in keywords if k in content.lower()) >= 2
    return False

router = DocumentRouter()
router.register_custom_function("is_financial_report", is_financial_report)
```

Then use it in routing_rules.yaml:

```yaml
- rule_id: financial_rule
  name: "Financial Reports"
  strategy: custom_function
  custom_function: is_financial_report
  target_store_id: financial
  priority: 25
```

### Forcing Store Routing

Override automatic routing:

```bash
curl -X POST http://localhost:8100/ingest/file \
  -H "Content-Type: application/json" \
  -d '{
    "filepath": "/path/to/document.pdf",
    "force_store_id": "specific_store"
  }'
```

This bypasses all routing rules and sends the document directly to the specified store.

### Processing Strategies

Choose the right strategy for your documents:

**auto (recommended)**:
- Automatically selects best strategy
- Good balance of speed and quality
```bash
"strategy": "auto"
```

**fast**:
- Faster processing
- Good for simple documents
- May miss complex tables or layouts
```bash
"strategy": "fast"
```

**hi_res**:
- High-resolution processing
- Best for complex documents with tables and images
- Slower but more accurate
```bash
"strategy": "hi_res"
```

**ocr_only**:
- Only uses OCR
- Best for scanned documents or images
- Requires readable images
```bash
"strategy": "ocr_only"
```

## Integration Examples

### Python Client

```python
import requests

def ingest_document(filepath, metadata=None):
    """Ingest a document via the API"""
    url = "http://localhost:8100/ingest/file"
    payload = {
        "filepath": filepath,
        "metadata": metadata or {},
        "strategy": "auto"
    }
    response = requests.post(url, json=payload)
    return response.json()

# Example usage
result = ingest_document(
    filepath="/data/meeting_notes.pdf",
    metadata={
        "date": "2024-10-08",
        "type": "meeting",
        "attendees": ["Alice", "Bob", "Carol"]
    }
)

print(f"Ingested to store: {result['store_id']}")
print(f"Document ID: {result['doc_id']}")
```

### Batch Ingestion Script

```bash
#!/bin/bash
# batch_ingest.sh

INGEST_URL="http://localhost:8100/ingest/file"
DATA_DIR="/path/to/documents"

for file in "$DATA_DIR"/*; do
    if [ -f "$file" ]; then
        echo "Ingesting: $file"

        curl -X POST "$INGEST_URL" \
          -H "Content-Type: application/json" \
          -d "{
            \"filepath\": \"$file\",
            \"strategy\": \"auto\"
          }"

        echo ""
    fi
done
```

### Watch Folder Integration

Monitor a folder and auto-ingest new files:

```python
import time
import os
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class IngestHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            print(f"New file detected: {event.src_path}")
            self.ingest_file(event.src_path)

    def ingest_file(self, filepath):
        url = "http://localhost:8100/ingest/file"
        payload = {"filepath": filepath, "strategy": "auto"}
        try:
            response = requests.post(url, json=payload)
            result = response.json()
            if result["success"]:
                print(f"✓ Ingested to {result['store_id']}")
            else:
                print(f"✗ Error: {result.get('error')}")
        except Exception as e:
            print(f"✗ Failed: {str(e)}")

# Watch directory
observer = Observer()
observer.schedule(IngestHandler(), "/data/incoming", recursive=False)
observer.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    observer.stop()
observer.join()
```

## Workflow Integration

Ingested documents are automatically available to workflows:

```bash
# 1. Ingest a meeting transcript
curl -X POST http://localhost:8100/ingest/file \
  -H "Content-Type: application/json" \
  -d '{
    "filepath": "/data/standup_notes.pdf",
    "metadata": {"type": "meeting", "team": "engineering"}
  }'

# Document automatically routed to "meetings" store

# 2. Query via workflow that accesses meetings store
curl -X POST http://localhost:8100/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What action items were discussed in the standup?",
    "workflow_id": "meeting_tracker",
    "user_id": "alice@company.com",
    "user_email": "alice@company.com",
    "user_roles": ["employee"]
  }'
```

The `meeting_tracker` workflow is configured to access the `meetings` store:

```yaml
workflows:
  meeting_tracker:
    name: "Meeting Insights"
    allowed_stores:
      - meetings  # Accesses documents ingested to meetings store
    required_roles:
      - employee
```

## Troubleshooting

### unstructured-api Not Responding

Check if the service is running:

```bash
# Check service status
docker-compose ps unstructured-api

# Check logs
docker-compose logs unstructured-api

# Restart service
docker-compose restart unstructured-api

# Test health
curl http://localhost:8001/healthcheck
```

### Document Not Being Routed Correctly

Check routing rules and priorities:

```bash
# View active rules
curl http://localhost:8100/ingest/routing-rules

# Check which rule matched
curl -X POST http://localhost:8100/ingest/file \
  -H "Content-Type: application/json" \
  -d '{"filepath": "/path/to/document.pdf"}' \
  | jq '.routing_info'
```

Output shows which rule matched:
```json
{
  "rule_id": "pdf_rule",
  "rule_name": "General PDFs",
  "confidence": 1.0
}
```

### No Text Extracted from PDF

Try different processing strategies:

```bash
# Try hi_res strategy for scanned PDFs
curl -X POST http://localhost:8100/ingest/file \
  -H "Content-Type: application/json" \
  -d '{
    "filepath": "/path/to/scanned.pdf",
    "strategy": "hi_res"
  }'

# Or use OCR-only for heavily scanned documents
curl -X POST http://localhost:8100/ingest/file \
  -H "Content-Type: application/json" \
  -d '{
    "filepath": "/path/to/scanned.pdf",
    "strategy": "ocr_only"
  }'
```

### Store Not Auto-Created

Check store configuration in routing_rules.yaml:

```yaml
store_configs:
  my_store:
    auto_create: true  # Must be true
    description: "My store"
    pii_level: partial
```

And ensure auto-creation is enabled:

```python
# In service initialization
ingestion_service = SmartIngestionService(
    ...,
    auto_create_stores=True  # Must be True
)
```

### Duplicate Detection Issues

Clear ingestion history if needed (testing only):

```python
from knowledge_system.ingestion import SmartIngestionService

await ingestion_service.clear_history()
```

## Best Practices

1. **Use Appropriate Strategies**
   - `auto` for most documents
   - `hi_res` for complex tables and layouts
   - `ocr_only` for scanned images

2. **Add Metadata**
   - Helps with routing and searchability
   - Include: title, author, date, classification, tags

3. **Configure Store Settings**
   - Set appropriate PII levels
   - Define required roles for sensitive stores
   - Enable audit logging for compliance

4. **Monitor Ingestion**
   - Check statistics regularly
   - Review routing accuracy
   - Adjust rules as needed

5. **Test Routing Rules**
   - Start with high-priority rules for important cases
   - Use catch-all rules at low priority
   - Test with sample documents

6. **Handle Errors Gracefully**
   - Check `success` field in responses
   - Log errors for review
   - Implement retry logic for transient failures

## Configuration Reference

### Environment Variables

```bash
# Unstructured API URL
UNSTRUCTURED_API_URL=http://unstructured-api:8000

# Routing rules configuration
ROUTING_RULES_PATH=/app/knowledge_system/examples/routing_rules.yaml

# Store auto-creation
AUTO_CREATE_STORES=true

# Default store for unmatched documents
DEFAULT_STORE_ID=general_documents
```

### Routing Rules Schema

```yaml
# routing_rules.yaml

default_store: general_documents

routing_rules:
  - rule_id: unique_identifier
    name: "Human-readable name"
    description: "Rule description"
    strategy: file_extension | metadata_field | content_pattern | custom_function

    # For file_extension strategy
    file_extensions:
      - pdf
      - docx

    # For metadata_field strategy
    metadata_field: classification
    metadata_values:
      - confidential

    # For content_pattern strategy
    content_patterns:
      - "(?i)regex pattern"

    # For custom_function strategy
    custom_function: function_name

    target_store_id: store_name
    priority: 50  # Lower = higher priority
    enabled: true

store_configs:
  store_name:
    description: "Store description"
    pii_level: none | partial | full | metadata_only
    audit_level: basic | detailed | forensic
    requires_roles:
      - role1
      - role2
    auto_create: true
```

## Summary

The smart ingestion system provides:

- **50+ file type support** via unstructured-api
- **Automatic routing** based on configurable rules
- **Store auto-creation** with appropriate security settings
- **Deduplication** to prevent duplicate processing
- **Metadata extraction** for better searchability
- **REST API** for easy integration

Start ingesting documents today with:

```bash
curl -X POST http://localhost:8100/ingest/file \
  -H "Content-Type: application/json" \
  -d '{"filepath": "/path/to/document.pdf", "strategy": "auto"}'
```
