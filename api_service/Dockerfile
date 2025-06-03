FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set PYTHONPATH to include current directory
ENV PYTHONPATH=/app

# Run the API service
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]