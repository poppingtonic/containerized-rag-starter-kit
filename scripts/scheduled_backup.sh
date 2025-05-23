#!/bin/bash
#
# GraphRAG PostgreSQL Database Scheduled Backup Script
# 
# This script is designed to be run via cron to create regular backups.
# It creates a compressed backup of the GraphRAG PostgreSQL database
# and implements rotation to keep only a specified number of backups.
#
# Recommended cron setup (daily at 2:00 AM):
# 0 2 * * * /path/to/scheduled_backup.sh
#
# Usage: ./scheduled_backup.sh [backup_directory] [retention_count]
#   backup_directory: Optional. Directory to store backups (default: ./backups)
#   retention_count: Optional. Number of backups to keep (default: 7)

set -e  # Exit immediately if a command exits with a non-zero status

# Configuration
BACKUP_DIR="${1:-./backups}"
RETENTION_COUNT="${2:-7}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${BACKUP_DIR}/backup_log.txt"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Function to log messages
log_message() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Log start of backup process
log_message "Starting scheduled backup..."

# Run the backup script
if "${SCRIPT_DIR}/backup_db.sh" "$BACKUP_DIR"; then
  log_message "Backup completed successfully"
else
  log_message "Backup failed"
  exit 1
fi

# Rotate old backups
log_message "Rotating backups, keeping the newest $RETENTION_COUNT"
backup_count=$(find "$BACKUP_DIR" -name "graphrag_backup_*.sql.gz" | wc -l)

if [ "$backup_count" -gt "$RETENTION_COUNT" ]; then
  # Delete oldest backups keeping only RETENTION_COUNT
  find "$BACKUP_DIR" -name "graphrag_backup_*.sql.gz" -type f -printf '%T@ %p\n' | \
    sort -n | head -n $(( backup_count - RETENTION_COUNT )) | \
    cut -d' ' -f2- | xargs rm -f
  
  log_message "Removed $(( backup_count - RETENTION_COUNT )) old backup(s)"
else
  log_message "No backups to rotate, current count: $backup_count"
fi

# Log completion
log_message "Scheduled backup completed"
exit 0