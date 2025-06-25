# GraphRAG Processor Deployment Guide

## Overview

This guide covers all deployment options for the GraphRAG processor, from CPU-only to GPU-accelerated versions.

## Prerequisites

### For GPU Deployment
- NVIDIA GPU with CUDA support
- NVIDIA Docker runtime installed
- CUDA 11.8 or compatible version
- At least 8GB GPU memory recommended

### For All Deployments
- Docker and Docker Compose
- Java Runtime (included in Dockerfiles)
- At least 4GB RAM
- OpenAI API key

## Deployment Options

### 1. GPU-Accelerated with Stanza + OpenIE (Recommended for Quality)

Best for production environments with GPU available.

```bash
# Deploy with CUDA support
docker compose -f docker-compose.yml -f docker-compose.cuda.yml up -d

# Verify GPU is being used
docker compose logs graphrag-processor | grep CUDA
```

**Features:**
- Full Stanza pipeline with neural coreference resolution
- Stanford OpenIE for rich relation extraction
- GPU-accelerated processing
- Sentence transformers on GPU
- Best quality and performance

### 2. CPU with OpenIE (Best CPU Quality)

For systems without GPU but needing good relation extraction.

```bash
# Deploy CPU version with OpenIE
docker compose -f docker-compose.yml -f docker-compose.cpu_openie.yml up -d
```

**Features:**
- Heuristic coreference resolution
- Stanford OpenIE for relation extraction
- CPU-optimized processing
- Good balance of quality and resource usage

### 3. Minimal CPU (Lowest Resources)

For resource-constrained environments.

```bash
# Deploy minimal CPU version
docker compose -f docker-compose.yml -f docker-compose.cpu.yml up -d
```

**Features:**
- No Java dependencies
- Stanza-only relation extraction
- Lowest memory footprint
- Fastest startup

### 4. Original spaCy Version (Legacy)

Keep using the original implementation.

```bash
# Use original docker-compose.yml
docker compose up -d
```

## Installation Steps

### Step 1: Check GPU Availability (Optional)
```bash
# Check if NVIDIA GPU is available
nvidia-smi

# Check Docker NVIDIA runtime
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

### Step 2: Configure Environment
```bash
# Copy example environment file
cp env.example .env

# Edit .env and add your OpenAI API key
echo "OPENAI_API_KEY=your-key-here" >> .env
```

### Step 3: Choose Deployment Method

#### Option A: Automatic Deployment
```bash
# For GPU
./deploy_gpu.sh

# For CPU with OpenIE
./deploy_cpu_openie.sh

# For minimal CPU
./deploy_cpu.sh
```

#### Option B: Manual Deployment
```bash
cd graphrag_processor

# Choose your version
cp app_stanza.py app.py  # For GPU/Stanza version
# OR
cp app_cpu_with_openie.py app.py  # For CPU with OpenIE
# OR
cp app_cpu.py app.py  # For minimal CPU

# Choose corresponding Dockerfile
cp Dockerfile.cuda Dockerfile  # For GPU
# OR
cp Dockerfile.cpu_openie Dockerfile  # For CPU with OpenIE
# OR
cp Dockerfile.cpu Dockerfile  # For minimal CPU

# Build and run
cd ..
docker compose up -d --build
```

## Performance Comparison

| Deployment | Processing Speed | Memory Usage | Quality | GPU Required |
|------------|-----------------|--------------|---------|--------------|
| GPU + Stanza + OpenIE | Fast (200-500 chunks/min) | 6-8GB | Excellent | Yes |
| CPU + OpenIE | Moderate (100-200 chunks/min) | 4-6GB | Good | No |
| Minimal CPU | Moderate (150-250 chunks/min) | 2-4GB | Fair | No |
| Original spaCy | Moderate (100-200 chunks/min) | 3-4GB | Fair | No |

## Monitoring and Troubleshooting

### Check Service Status
```bash
# View all services
docker compose ps

# Check logs
docker compose logs -f graphrag-processor

# Monitor resource usage
docker stats graphrag-processor
```

### GPU Monitoring
```bash
# Monitor GPU usage
nvidia-smi -l 1

# Check if container sees GPU
docker compose exec graphrag-processor python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
```

### Common Issues

#### GPU Not Detected
```bash
# Ensure NVIDIA Docker runtime is installed
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# Check Docker daemon configuration
cat /etc/docker/daemon.json
# Should contain: "default-runtime": "nvidia"
```

#### Out of Memory
```bash
# Reduce batch size
docker compose exec graphrag-processor bash
export BATCH_SIZE=16
python app.py
```

#### Java/OpenIE Issues
```bash
# Check Java installation
docker compose exec graphrag-processor java -version

# Verify CoreNLP installation
docker compose exec graphrag-processor ls -la /opt/corenlp
```

## Configuration Options

### Environment Variables

| Variable | Description | Default | Applies To |
|----------|-------------|---------|------------|
| `OPENAI_API_KEY` | OpenAI API key | Required | All |
| `PROCESSING_INTERVAL` | Seconds between processing runs | 3600 | All |
| `BATCH_SIZE` | Chunks processed per batch | 32 | CPU versions |
| `MAX_TEXT_LENGTH` | Maximum text length per chunk | 5000 | CPU versions |
| `USE_OPENIE` | Enable/disable OpenIE | true | CPU+OpenIE |
| `CUDA_VISIBLE_DEVICES` | GPU device selection | 0 | GPU version |

### Resource Limits

Adjust in docker-compose files:
```yaml
deploy:
  resources:
    limits:
      cpus: '4'
      memory: 8G
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

## Migration Between Versions

### From Original to Stanza GPU
```bash
# Backup current data
docker compose exec db pg_dump -U graphraguser graphragdb > backup.sql

# Switch to Stanza version
cd graphrag_processor
./migrate_to_stanza.sh

# Deploy with GPU
cd ..
docker compose -f docker-compose.yml -f docker-compose.cuda.yml up -d
```

### From GPU to CPU
```bash
# Simply change the compose file
docker compose down
docker compose -f docker-compose.yml -f docker-compose.cpu_openie.yml up -d
```

## Best Practices

1. **Start with GPU version** if available for best quality
2. **Use CPU+OpenIE** for good quality without GPU
3. **Monitor memory usage** and adjust batch sizes accordingly
4. **Schedule processing** during off-peak hours for large datasets
5. **Backup regularly** before switching versions

## Testing Deployment

```bash
# Test NER and relation extraction
docker compose exec graphrag-processor python -c "
from app import process_text_with_stanza, extract_relations_openie
text = 'Apple Inc. was founded by Steve Jobs in Cupertino, California.'
resolved, entities = process_text_with_stanza(text)
print(f'Entities: {entities}')
print(f'Resolved text: {resolved}')
"

# Check output generation
ls -la $(docker volume inspect writehere-graphrag_graphrag_data --format '{{ .Mountpoint }}')/
```