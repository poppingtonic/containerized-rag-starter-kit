FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for Stanza and OpenIE
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    default-jre \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements_stanza.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements_stanza.txt

# Download Stanford CoreNLP for OpenIE (required by stanford-openie)
RUN cd /tmp && \
    wget https://nlp.stanford.edu/software/stanford-corenlp-4.5.5.zip && \
    unzip stanford-corenlp-4.5.5.zip && \
    mv stanford-corenlp-4.5.5 /opt/corenlp && \
    rm stanford-corenlp-4.5.5.zip

# Set environment variable for Stanford CoreNLP
ENV CORENLP_HOME=/opt/corenlp

# Copy application code
COPY app.py app.py

# Create output directory
RUN mkdir -p /app/outputs

# Pre-download Stanza models during build
RUN python -c "import stanza; stanza.download('en', verbose=False)"

# Run the GraphRAG processor
CMD ["python", "app.py"]