#!/bin/bash
#
# GraphRAG PostgreSQL Database Backup Script
# 
# This script creates a compressed backup of the GraphRAG PostgreSQL database.
# It works both when the database is running in a Docker container or directly.
#
# Usage: ./backup_db.sh [backup_directory]
#   backup_directory: Optional. Directory to store backups (default: ./backups)

set -e  # Exit immediately if a command exits with a non-zero status

# Configuration
DB_NAME="graphragdb"
DB_USER="graphraguser"
DB_PASSWORD="graphragpassword"
DB_HOST="localhost"
DB_PORT="5433"
CONTAINER_NAME="writehere-graphrag-db-1"  # Default container name from docker-compose
DOCKER_RUNNING=false
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="${1:-./backups}"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"
echo "✅ Backup directory: $BACKUP_DIR"

# Function to check if Docker is running and the container exists
check_docker() {
  if command -v docker &> /dev/null && docker ps &> /dev/null; then
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
      DOCKER_RUNNING=true
      echo "✅ Found Docker container: $CONTAINER_NAME"
    fi
  fi
}

# Function to perform backup using Docker
backup_with_docker() {
  echo "🔄 Backing up database via Docker container..."
  BACKUP_FILE="${BACKUP_DIR}/graphrag_backup_${TIMESTAMP}.sql"
  
  docker exec -t "$CONTAINER_NAME" pg_dump -U "$DB_USER" -d "$DB_NAME" > "$BACKUP_FILE"
  
  if [ $? -eq 0 ]; then
    echo "✅ Database backup created: $BACKUP_FILE"
    echo "🔄 Compressing backup..."
    gzip "$BACKUP_FILE"
    echo "✅ Backup compressed: ${BACKUP_FILE}.gz"
  else
    echo "❌ Failed to create database backup via Docker"
    exit 1
  fi
}

# Function to perform backup directly
backup_directly() {
  echo "🔄 Backing up database directly..."
  BACKUP_FILE="${BACKUP_DIR}/graphrag_backup_${TIMESTAMP}.sql"
  
  PGPASSWORD="$DB_PASSWORD" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" > "$BACKUP_FILE"
  
  if [ $? -eq 0 ]; then
    echo "✅ Database backup created: $BACKUP_FILE"
    echo "🔄 Compressing backup..."
    gzip "$BACKUP_FILE"
    echo "✅ Backup compressed: ${BACKUP_FILE}.gz"
  else
    echo "❌ Failed to create database backup directly"
    exit 1
  fi
}

# Main execution
echo "🔄 Starting GraphRAG database backup process..."

# Check for Docker container
check_docker

# Perform backup using the appropriate method
if [ "$DOCKER_RUNNING" = true ]; then
  backup_with_docker
else
  echo "ℹ️ Docker container not found, attempting direct database connection"
  # Check if pg_dump is available
  if command -v pg_dump &> /dev/null; then
    backup_directly
  else
    echo "❌ pg_dump command not found. Please install PostgreSQL client tools"
    exit 1
  fi
fi

echo "✅ Backup process completed successfully!"
echo "📁 Backup location: ${BACKUP_DIR}/graphrag_backup_${TIMESTAMP}.sql.gz"
exit 0