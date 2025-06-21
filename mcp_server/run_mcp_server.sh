#!/bin/bash

# MCP Server startup script for Consilience

echo "Starting Consilience MCP Server..."

# Set environment variables if not already set
export PYTHONPATH="${PYTHONPATH}:/app"
export INGESTION_SERVICE_URL="${INGESTION_SERVICE_URL:-http://ingestion-service:5050}"

# Wait for API service to be ready (optional, but recommended)
echo "Waiting for API service..."
while ! curl -s http://api-service:8000/health > /dev/null; do
    sleep 1
done
echo "API service is ready!"

# Start the MCP server
exec python /app/mcp_server/server.py