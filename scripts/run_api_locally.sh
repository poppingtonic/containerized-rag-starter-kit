#!/bin/bash

# Script to run the API service locally for testing

# Set environment variables
export DATABASE_URL="postgresql://graphraguser:graphragpassword@localhost:5433/graphragdb"
export OPENAI_API_KEY="your_openai_api_key_here"
export GRAPH_OUTPUT_PATH="/home/mu/src/writehere-graphrag/data/graph_outputs"

# Create the graph output directory if it doesn't exist
mkdir -p "$GRAPH_OUTPUT_PATH"

# Navigate to the API service directory
cd /home/mu/src/writehere-graphrag/api_service

# Install dependencies if not already installed
if [ ! -f "./.dependencies_installed" ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
    touch ./.dependencies_installed
fi

# Run the API with Uvicorn
echo "Starting API server at http://localhost:8000..."
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload