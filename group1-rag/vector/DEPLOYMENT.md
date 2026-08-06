# Deployment Guide — Qdrant Vector Client

Production deployment guide for Group One RAG vector database client.

## Prerequisites

- Python 3.9+
- Docker & Docker Compose (for Qdrant)
- 4GB+ RAM
- Linux/macOS/Windows with WSL2

## Local Development Setup

### 1. Start Qdrant Server

**Using Docker Compose** (Recommended):

```bash
# Create docker-compose.yml
cat > docker-compose.yml << 'EOF'
version: '3.8'
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant-storage:/qdrant/storage
    environment:
      - QDRANT_TELEMETRY_DISABLED=true
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 5s
      timeout: 2s
      retries: 3

volumes:
  qdrant-storage:
EOF

# Start Qdrant
docker-compose up -d qdrant

# Verify it's running
curl http://localhost:6333/health
```

**Using Docker CLI**:

```bash
docker run -p 6333:6333 -p 6334:6334 \
  -v qdrant-storage:/qdrant/storage \
  qdrant/qdrant:latest
```

### 2. Install Dependencies

```bash
# Navigate to vector directory
cd /workspace/group1-rag/vector

# Install requirements
pip install -r requirements.txt

# Or install with development tools
pip install -r requirements.txt pytest pytest-cov black pylint
```

### 3. Run Tests

```bash
# Run all tests
make test

# Run with coverage
make test-coverage

# Run specific tests
make test-chunker
make test-embedding
make test-store
```

### 4. Try Example Usage

```bash
# Ensure Qdrant is running
python example_usage.py
```

## Development Workflow

### 1. Code Changes

```bash
# Make changes to vector_client.py or other files
# Run tests to verify
make test

# Check for syntax errors
make check

# Format code
make format
```

### 2. Testing New Features

```bash
# Add test to test_vector.py
# Run specific test
pytest test_vector.py::TestYourNewFeature -v

# Run full test suite
make test-coverage
```

### 3. Performance Benchmarking

```bash
# Run latency benchmarks
make test-latency

# Run example with stats
python example_usage.py 2>&1 | grep -i "latency\|throughput"
```

## Staging Deployment

### 1. Prepare Environment

```bash
# Create staging directory
mkdir -p /srv/staging/group1-rag-vector

# Copy files
cp -r /workspace/group1-rag/vector/* /srv/staging/group1-rag-vector/

# Install dependencies
cd /srv/staging/group1-rag-vector
pip install -r requirements.txt
```

### 2. Configure Qdrant

**docker-compose.yml for staging**:

```yaml
version: '3.8'
services:
  qdrant-staging:
    image: qdrant/qdrant:latest
    ports:
      - "6334:6333"  # Different port for staging
    volumes:
      - qdrant-staging:/qdrant/storage
    environment:
      - QDRANT_TELEMETRY_DISABLED=true
      - QDRANT_API_KEY=staging-key-change-this
    restart: unless-stopped

volumes:
  qdrant-staging:
```

### 3. Ingest Staging Data

```python
from vector_client import QdrantVectorStore
from pathlib import Path

# Initialize with staging server
vector_store = QdrantVectorStore(
    collection_name="group1-rag-staging",
    host="localhost",
    port=6334,
    embedding_model='finbert',
    recreate_collection=True  # Fresh staging
)

# Ingest corpus files
stats = vector_store.ingest_corpus_files(
    corpus_dir=Path("/workspace/corpus/financial-services"),
    domain="finance",
    batch_size=100
)

print(f"Staged {stats['chunks_ingested']} chunks")
```

### 4. Run Staging Tests

```bash
# Set environment variable for staging
export QDRANT_HOST="localhost"
export QDRANT_PORT="6334"

# Run tests against staging
python -m pytest test_vector.py -v

# Run example queries
python example_usage.py
```

## Production Deployment

### 1. Production Server Setup

**docker-compose.yml for production**:

```yaml
version: '3.8'
services:
  qdrant-prod:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant-prod-storage:/qdrant/storage
    environment:
      - QDRANT_TELEMETRY_DISABLED=true
      - QDRANT_API_KEY=${QDRANT_API_KEY}  # From .env file
      - QDRANT_READ_ONLY=false
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "-H", "api-key: ${QDRANT_API_KEY}", "http://localhost:6333/health"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - rag-network

  vector-client:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - QDRANT_HOST=qdrant-prod
      - QDRANT_PORT=6333
      - QDRANT_API_KEY=${QDRANT_API_KEY}
      - LOG_LEVEL=INFO
    depends_on:
      qdrant-prod:
        condition: service_healthy
    networks:
      - rag-network
    restart: always

networks:
  rag-network:
    driver: bridge

volumes:
  qdrant-prod-storage:
    driver: local
```

### 2. Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY vector_client.py .
COPY __init__.py .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from vector_client import QdrantVectorStore; QdrantVectorStore().health_check()" || exit 1

# Run application (as imported module)
CMD ["python", "-m", "vector_client"]
```

### 3. Environment Configuration

**Create .env file**:

```bash
# Qdrant Configuration
QDRANT_HOST=qdrant-prod
QDRANT_PORT=6333
QDRANT_API_KEY=your-secure-api-key-here
QDRANT_TIMEOUT=30.0

# Embedding Model
EMBEDDING_MODEL=finbert
FALLBACK_MODEL=bge-large-en-v1.5

# Collection
COLLECTION_NAME=group1-rag
RECREATE_COLLECTION=false

# Logging
LOG_LEVEL=INFO

# OpenAI (if using text-embedding-3-large)
OPENAI_API_KEY=sk-...
```

### 4. Deploy to Production

```bash
# Pull latest code
cd /srv/production/group1-rag-vector
git pull origin main

# Build and start services
docker-compose -f docker-compose.yml up -d

# Verify services are running
docker-compose ps

# Check logs
docker-compose logs -f qdrant-prod
docker-compose logs -f vector-client
```

### 5. Initial Data Load

```python
# Run from production environment
from vector_client import QdrantVectorStore
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)

vector_store = QdrantVectorStore(
    collection_name="group1-rag",
    host="qdrant-prod",
    port=6333,
    embedding_model='finbert',
    recreate_collection=True  # Only for initial load
)

# Ingest production data
corpus_dirs = [
    Path("/data/corpus/finance"),
    Path("/data/corpus/financial-services"),
    Path("/data/corpus/trading"),
]

for corpus_dir in corpus_dirs:
    if corpus_dir.exists():
        stats = vector_store.ingest_corpus_files(
            corpus_dir=corpus_dir,
            domain=corpus_dir.name,
            batch_size=100
        )
        print(f"Loaded {stats['chunks_ingested']} chunks from {corpus_dir}")

# Verify
health = vector_store.health_check()
print(f"Collection ready: {health['document_count']} documents")
```

## Monitoring & Operations

### 1. Health Checks

```bash
# Check Qdrant health
curl -H "api-key: $QDRANT_API_KEY" http://localhost:6333/health

# Check collection status
curl -H "api-key: $QDRANT_API_KEY" http://localhost:6333/collections/group1-rag
```

### 2. Performance Monitoring

```python
from vector_client import QdrantVectorStore

vector_store = QdrantVectorStore()

# Get statistics
stats = vector_store.get_stats()
print(f"Documents: {stats['documents_ingested']}")
print(f"Chunks: {stats['chunks_ingested']}")
print(f"Avg Query Latency: {stats['avg_query_time_ms']:.2f}ms")

# Health check
health = vector_store.health_check()
if health['status'] != 'healthy':
    # Alert!
    pass
```

### 3. Logging

```python
import logging

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
)

# For JSON parsing by log aggregators
import json
logger = logging.getLogger('vector-client')
```

### 4. Alerting

**Prometheus metrics** (future enhancement):

```python
# TODO: Implement Prometheus metrics export
from prometheus_client import Counter, Histogram, Gauge

query_latency = Histogram(
    'vector_query_latency_ms',
    'Query latency in milliseconds',
    buckets=[10, 20, 50, 100, 200]
)

ingestion_rate = Counter(
    'vector_chunks_ingested_total',
    'Total chunks ingested'
)

collection_size = Gauge(
    'vector_collection_size_documents',
    'Number of documents in collection'
)
```

## Scaling Considerations

### Single Qdrant Instance

**Suitable for**:
- Up to 100k documents
- <1000 QPS
- Single deployment region

**Limitations**:
- No horizontal scaling
- Single point of failure
- Limited to one machine's resources

### Multi-Collection Approach

For multiple isolated datasets:

```python
# Separate collections for different domains
store_finance = QdrantVectorStore(collection_name="group1-finance")
store_trading = QdrantVectorStore(collection_name="group1-trading")
```

### Future: Multi-Instance Setup

For higher scale:

1. **Sharding**: Partition documents by domain/date
2. **Replication**: Multi-master replication (Qdrant Cloud)
3. **Load Balancing**: Route queries by collection name

## Backup & Disaster Recovery

### 1. Automated Backups

```bash
# Backup Qdrant data directory
#!/bin/bash
BACKUP_DIR="/backups/qdrant"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

docker-compose exec -T qdrant-prod \
  tar czf - /qdrant/storage | \
  gzip > "$BACKUP_DIR/qdrant_$TIMESTAMP.tar.gz"

# Keep last 7 days
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete
```

### 2. Point-in-Time Recovery

```bash
# Restore from backup
BACKUP_FILE="/backups/qdrant/qdrant_20240806_120000.tar.gz"

# Stop services
docker-compose down

# Restore data
rm -rf qdrant-storage/*
tar xzf "$BACKUP_FILE" -C qdrant-storage/

# Start services
docker-compose up -d
```

## Troubleshooting

### Connection Issues

```bash
# Test Qdrant connectivity
curl -v http://localhost:6333/health

# Check Docker logs
docker logs qdrant-prod

# Restart service
docker-compose restart qdrant-prod
```

### Slow Queries

```python
# Profile query latency
import time
vector_store = QdrantVectorStore()

for _ in range(100):
    start = time.time()
    vector_store.query("test", top_k=5)
    latency = (time.time() - start) * 1000
    if latency > 100:
        print(f"Slow query: {latency:.2f}ms")

# Check statistics
stats = vector_store.get_stats()
print(f"Average: {stats['avg_query_time_ms']:.2f}ms")
```

### Memory Issues

```bash
# Monitor container memory
docker stats qdrant-prod

# Increase memory limit in docker-compose.yml
# Add to qdrant service:
# deploy:
#   resources:
#     limits:
#       memory: 8G
#     reservations:
#       memory: 4G
```

## Rollback Procedures

### 1. Rollback to Previous Version

```bash
# Stop current deployment
docker-compose down

# Checkout previous version
git checkout HEAD~1

# Rebuild and restart
docker-compose up -d

# Verify
docker-compose logs qdrant-prod
```

### 2. Rollback Qdrant Data

```bash
# If data is corrupted, restore from backup
./scripts/restore-backup.sh qdrant_20240806_110000.tar.gz

# Verify collection
curl -H "api-key: $QDRANT_API_KEY" \
  http://localhost:6333/collections/group1-rag
```

## Maintenance Windows

### Scheduled Maintenance

```bash
# 1. Announce maintenance window
# 2. Stop accepting new ingestions
# 3. Flush pending operations

docker-compose exec qdrant-prod \
  curl -X POST http://localhost:6333/collections/group1-rag/snapshots

# 4. Back up data
# 5. Perform upgrades
# 6. Verify functionality
# 7. Resume operations
```

### Collection Optimization

```bash
# Force index optimization (future Qdrant feature)
# Reduces memory usage, improves query speed

# Estimated time: ~30 minutes for 100k documents
# Best done during low-traffic periods
```

## Security Hardening

### 1. Network Security

```yaml
# In docker-compose.yml
services:
  qdrant:
    networks:
      - internal  # Don't expose to public
    ports:
      - "127.0.0.1:6333:6333"  # Localhost only
```

### 2. API Authentication

```python
# Use API key in all requests
vector_store = QdrantVectorStore(
    host="qdrant-prod",
    api_key=os.getenv('QDRANT_API_KEY')
)
```

### 3. TLS/HTTPS

```yaml
# For production Qdrant Cloud
qdrant-prod:
  environment:
    - QDRANT_HTTPS=true
    - QDRANT_CERT_PATH=/etc/qdrant/certs/
```

---

**Last Updated**: 2024-08-06
**Version**: 1.0.0
