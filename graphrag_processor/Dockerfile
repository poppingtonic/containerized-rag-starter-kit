FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install spaCy model
RUN python -m spacy download en_core_web_sm

# Copy application code
COPY . .

# Create output directory
RUN mkdir -p /app/outputs

# Run the GraphRAG processor
CMD ["python", "app.py"]