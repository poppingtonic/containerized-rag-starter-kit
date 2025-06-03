#!/bin/bash
#
# GraphRAG PostgreSQL Database Restore Script
# 
# This script restores a compressed backup of the GraphRAG PostgreSQL database.
# It works both when the database is running in a Docker container or directly.
#
# Usage: ./restore_db.sh <backup_file>
#   backup_file: Path to the compressed backup file (.sql.gz)

set -e  # Exit immediately if a command exits with a non-zero status

# Configuration
DB_NAME="graphragdb"
DB_USER="graphraguser"
DB_PASSWORD="graphragpassword"
DB_HOST="localhost"
DB_PORT="5433"
CONTAINER_NAME="writehere-graphrag-db-1"  # Default container name from docker-compose
DOCKER_RUNNING=false
TEMP_DIR="/tmp/graphrag_restore"

# Check if backup file was provided
if [ $# -eq 0 ]; then
  echo "❌ Error: No backup file provided"
  echo "Usage: $0 <backup_file>"
  exit 1
fi

BACKUP_FILE="$1"

# Check if the backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
  echo "❌ Error: Backup file not found: $BACKUP_FILE"
  exit 1
fi

# Function to check if Docker is running and the container exists
check_docker() {
  if command -v docker &> /dev/null && docker ps &> /dev/null; then
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
      DOCKER_RUNNING=true
      echo "✅ Found Docker container: $CONTAINER_NAME"
    fi
  fi
}

# Function to prepare backup file
prepare_backup() {
  echo "🔄 Preparing backup file..."
  
  # Create temporary directory
  mkdir -p "$TEMP_DIR"
  
  # Check if the file is compressed
  if [[ "$BACKUP_FILE" == *.gz ]]; then
    echo "🔄 Decompressing backup file..."
    gunzip -c "$BACKUP_FILE" > "${TEMP_DIR}/backup.sql"
    UNCOMPRESSED_BACKUP="${TEMP_DIR}/backup.sql"
  else
    # If it's already uncompressed, just copy it
    cp "$BACKUP_FILE" "${TEMP_DIR}/backup.sql"
    UNCOMPRESSED_BACKUP="${TEMP_DIR}/backup.sql"
  fi
  
  echo "✅ Backup file prepared: $UNCOMPRESSED_BACKUP"
  return 0
}

# Function to restore using Docker
restore_with_docker() {
  echo "🔄 Restoring database via Docker container..."
  
  # Copy the backup file to the container
  docker cp "$UNCOMPRESSED_BACKUP" "${CONTAINER_NAME}:/tmp/backup.sql"
  
  echo "⚠️ WARNING: This will overwrite the current database. Proceed? [y/N]"
  read -r confirm
  if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "❌ Restore cancelled"
    exit 1
  fi
  
  # Drop and recreate the database
  echo "🔄 Dropping existing database..."
  docker exec -t "$CONTAINER_NAME" psql -U "$DB_USER" -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME';"
  docker exec -t "$CONTAINER_NAME" psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS $DB_NAME;"
  echo "🔄 Creating new database..."
  docker exec -t "$CONTAINER_NAME" psql -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;"
  
  # Restore the database
  echo "🔄 Restoring database from backup..."
  docker exec -t "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -f "/tmp/backup.sql"
  
  if [ $? -eq 0 ]; then
    echo "✅ Database restored successfully"
    # Clean up
    docker exec -t "$CONTAINER_NAME" rm "/tmp/backup.sql"
  else
    echo "❌ Failed to restore database via Docker"
    exit 1
  fi
}

# Function to restore directly
restore_directly() {
  echo "🔄 Restoring database directly..."
  
  echo "⚠️ WARNING: This will overwrite the current database. Proceed? [y/N]"
  read -r confirm
  if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "❌ Restore cancelled"
    exit 1
  fi
  
  # Drop and recreate the database
  echo "🔄 Dropping existing database..."
  PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME';"
  PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -c "DROP DATABASE IF EXISTS $DB_NAME;"
  echo "🔄 Creating new database..."
  PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;"
  
  # Restore the database
  echo "🔄 Restoring database from backup..."
  PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$UNCOMPRESSED_BACKUP"
  
  if [ $? -eq 0 ]; then
    echo "✅ Database restored successfully"
  else
    echo "❌ Failed to restore database directly"
    exit 1
  fi
}

# Main execution
echo "🔄 Starting GraphRAG database restore process..."

# Prepare the backup file
prepare_backup

# Check for Docker container
check_docker

# Perform restore using the appropriate method
if [ "$DOCKER_RUNNING" = true ]; then
  restore_with_docker
else
  echo "ℹ️ Docker container not found, attempting direct database connection"
  # Check if psql is available
  if command -v psql &> /dev/null; then
    restore_directly
  else
    echo "❌ psql command not found. Please install PostgreSQL client tools"
    exit 1
  fi
fi

# Clean up
echo "🔄 Cleaning up temporary files..."
rm -rf "$TEMP_DIR"

echo "✅ Restore process completed successfully!"
exit 0