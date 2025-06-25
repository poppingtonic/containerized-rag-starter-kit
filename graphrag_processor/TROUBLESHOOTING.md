# GraphRAG Processor Troubleshooting Guide

## Common Issues and Solutions

### PyTorch Version Conflicts

**Error**: `Disabling PyTorch because PyTorch >= 2.1 is required`

**Solution**: 
The sentence-transformers library requires PyTorch 2.1.0 or higher. All Dockerfiles have been updated to use compatible versions:
- CUDA version: `torch==2.1.0+cu118`
- CPU version: `torch==2.1.0+cpu`

If you still encounter issues:
```bash
# Rebuild without cache
docker compose build --no-cache graphrag-processor
```

### Sentence Transformer Model Download

**Issue**: Model download fails during Docker build

**Solution**: 
The model will be downloaded on first run instead of during build. This is intentional to avoid version conflicts.

To manually test:
```bash
docker compose exec graphrag-processor python test_pytorch.py
```

### CUDA/GPU Issues

**Error**: `CUDA runtime error` or GPU not detected

**Solutions**:

1. Verify NVIDIA Docker runtime:
```bash
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

2. Check Docker daemon configuration:
```bash
cat /etc/docker/daemon.json
# Should contain: "default-runtime": "nvidia"
```

3. Restart Docker:
```bash
sudo systemctl restart docker
```

### Stanford OpenIE Issues

**Error**: `Failed to initialize OpenIE`

**Solutions**:

1. Verify Java is installed:
```bash
docker compose exec graphrag-processor java -version
```

2. Check CoreNLP installation:
```bash
docker compose exec graphrag-processor ls -la /opt/corenlp/
```

3. Use CPU version without OpenIE:
```bash
docker compose -f docker-compose.yml -f docker-compose.cpu.yml up -d
```

### Memory Issues

**Error**: `RuntimeError: CUDA out of memory` or container killed

**Solutions**:

1. Reduce batch size:
```bash
# In docker-compose file, add:
environment:
  - BATCH_SIZE=16
  - MAX_TEXT_LENGTH=3000
```

2. Use CPU version:
```bash
./deploy_cpu_openie.sh
```

3. Increase Docker memory limit:
```bash
# In docker-compose file:
deploy:
  resources:
    limits:
      memory: 8G
```

### Stanza Model Download Issues

**Error**: `HTTPError` when downloading Stanza models

**Solution**:
```bash
# Manual download inside container
docker compose exec graphrag-processor python -c "import stanza; stanza.download('en', verbose=True)"
```

### Build Failures

**General build troubleshooting**:

1. Clean Docker cache:
```bash
docker system prune -a
docker volume prune
```

2. Check disk space:
```bash
df -h
```

3. Build with verbose output:
```bash
docker compose build --no-cache --progress=plain graphrag-processor
```

### Testing the Installation

Run the test script to verify everything is working:

```bash
# Copy test script to container
docker compose cp test_pytorch.py graphrag-processor:/app/

# Run tests
docker compose exec graphrag-processor python test_pytorch.py
```

Expected output:
```
Testing PyTorch installation...
✓ PyTorch version: 2.1.0+cu118
  CUDA available: True
  CUDA device: NVIDIA GeForce RTX 3090

Testing sentence-transformers...
✓ sentence-transformers imported successfully
  Initializing test model...
✓ Model loaded on device: cuda
✓ Test encoding successful, embedding shape: (384,)

All tests passed! PyTorch and sentence-transformers are working correctly.
```

### Performance Issues

**Slow processing**:

1. Check if GPU is being used:
```bash
docker compose exec graphrag-processor nvidia-smi
```

2. Monitor resource usage:
```bash
docker stats graphrag-processor
```

3. Adjust thread counts for CPU:
```bash
# In environment variables:
OMP_NUM_THREADS=8
MKL_NUM_THREADS=8
```

### Debugging

Enable debug logging:

```bash
# Add to docker-compose environment:
environment:
  - PYTHONUNBUFFERED=1
  - TRANSFORMERS_VERBOSITY=debug
  - STANZA_LOGLEVEL=debug
```

View detailed logs:
```bash
docker compose logs -f --tail=100 graphrag-processor
```

### Getting Help

If issues persist:

1. Check container logs:
```bash
docker compose logs graphrag-processor > graphrag_error.log
```

2. Inspect container:
```bash
docker compose exec graphrag-processor /bin/bash
```

3. Test individual components:
```bash
# Test Stanza
docker compose exec graphrag-processor python -c "import stanza; print(stanza.__version__)"

# Test OpenIE
docker compose exec graphrag-processor python -c "from stanford_openie import StanfordOpenIE; print('OpenIE OK')"

# Test GPU
docker compose exec graphrag-processor python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
```