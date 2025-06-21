FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY mcp_server/requirements.txt /app/mcp_server/
RUN pip install --no-cache-dir -r mcp_server/requirements.txt

# Copy the entire project (needed for imports)
COPY . /app/

# Set Python path to include the app directory
ENV PYTHONPATH=/app

# Run the MCP server
CMD ["python", "mcp_server/server.py"]