# GraphRAG Utility Scripts

This directory contains utility scripts for managing and maintaining the GraphRAG system.

## Service Management

### `restart_service.sh`

A utility for restarting specific services in the GraphRAG system.

```bash
# Usage
./restart_service.sh [service_name] [--build] [--no-logs]

# Available services:
# - db
# - ingestion-service
# - graphrag-processor
# - api-service
# - frontend
# - ocr-service
# - all (restarts all services)

# Examples:
# Restart GraphRAG processor
./restart_service.sh graphrag-processor

# Rebuild and restart API service
./restart_service.sh api-service --build

# Restart all services without showing logs
./restart_service.sh all --no-logs

# Show help information
./restart_service.sh --help
```

## Import Utilities

### `watch_files.py`

Monitors a directory for new document files and copies them to the data directory for processing.

```bash
# Usage
./watch_files.py [options]

# Options
# -w, --watch-dir DIR: Directory to watch for new files (default: ~/Documents)
# -d, --data-dir DIR: Directory to copy files to (default: ./data)
# -s, --state-file FILE: File to store processing state (default: .processed_files.json)
# -e, --error-log FILE: File to log processing errors (default: .error_log.json)
# -r, --recursive: Watch directory recursively
# -t, --trigger-api: Trigger the ingestion API after copying files
# -p, --process-existing: Process existing files in the watch directory on startup

# Examples:
# Watch your Downloads folder and copy files to the data directory
./watch_files.py --watch-dir ~/Downloads --data-dir ./data

# Process all existing files in the watch directory and monitor for new ones
./watch_files.py --watch-dir ~/Documents --process-existing

# Watch recursively and trigger the ingestion API whenever new files are copied
./watch_files.py --watch-dir ~/Documents --recursive --trigger-api

# Run as a daemon in the background
nohup ./watch_files.py --watch-dir ~/Documents --recursive > watch_files.log 2>&1 &
```

### `import_documents.sh`

Basic document importer script.

```bash
# Import PDF documents from a Zotero directory
./import_documents.sh /path/to/zotero/storage
```

### `import_with_metadata.py`

Advanced importer with metadata preservation.

```bash
# Import with metadata
python ./import_with_metadata.py /path/to/documents

# Preserve directory structure
python ./import_with_metadata.py --preserve-structure /path/to/documents

# Custom target directory
python ./import_with_metadata.py --target-dir ./custom_data_dir /path/to/documents
```

### `import_with_ocr.py`

Import documents with OCR processing.

```bash
# Import with OCR support
python ./import_with_ocr.py /path/to/documents

# Force OCR for all documents
python ./import_with_ocr.py --force-ocr /path/to/documents

# Disable OCR
python ./import_with_ocr.py --no-ocr /path/to/documents

# Adjust processing threads
python ./import_with_ocr.py --threads 8 /path/to/documents
```

## Database Management

### `backup_db.sh`

Creates a compressed backup of the PostgreSQL database.

```bash
# Create a backup in the default directory (./backups)
./backup_db.sh

# Create a backup in a specific directory
./backup_db.sh /path/to/backup/directory
```

### `restore_db.sh`

Restores a database from a previously created backup.

```bash
# Restore from a backup file
./restore_db.sh /path/to/backup.sql.gz
```

### `scheduled_backup.sh`

Creates regular backups with rotation, designed to be used with cron.

```bash
# Default: Keep 7 backups in ./backups
./scheduled_backup.sh

# Custom backup directory and retention count
./scheduled_backup.sh /custom/backup/path 14

# Example crontab entry (run daily at 2:00 AM)
# 0 2 * * * /full/path/to/scheduled_backup.sh /full/path/to/backup/directory 7
```

## Diagnostic Tools

### `check_ingestion.sh`

Utility for checking the status of document ingestion.

```bash
# Check ingestion status
./check_ingestion.sh
```

## Development Helpers

### `run_api_locally.sh`

Runs the API service directly on the host instead of in a container.

```bash
# Run the API service locally
./run_api_locally.sh
```