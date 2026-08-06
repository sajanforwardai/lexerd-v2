# Group One Trading RAG - 30-Minute Quickstart

**Time Required:** 30 minutes  
**Difficulty:** Beginner  
**Scope:** Full stack deployment (development environment)

---

## Prerequisites (5 minutes)

### Software Requirements

```bash
# Check versions
docker --version  # >= 20.10
docker-compose --version  # >= 1.29

# Install if needed
# macOS
brew install docker docker-compose

# Ubuntu/Debian
sudo apt-get install docker.io docker-compose

# Verify installation
docker run hello-world
```

### AWS Setup (if enabling backups)

```bash
# Install AWS CLI
pip install awscli

# Configure credentials
aws configure
# Enter: AWS Access Key ID
# Enter: AWS Secret Access Key
# Enter: Default region (us-east-1)
# Enter: Default output format (json)

# Verify
aws s3 ls
```

---

## Step 1: Clone & Setup (2 minutes)

```bash
# Navigate to project
cd /workspace/group1-rag/enterprise

# Copy environment file
cp .env.example .env

# View the file
cat .env

# Make it executable
chmod +x *.py
```

### Edit Configuration

```bash
# Open .env in your editor
nano .env

# CRITICAL: Change these values:
SECRET_KEY=my-super-secret-key-$(date +%s)
DB_PASSWORD=postgres-password-$(date +%s)

# For AWS backups (optional):
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
S3_BUCKET=my-rag-backups-$(date +%s)

# For Slack alerts (optional):
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Save and exit
# nano: Ctrl+O, Enter, Ctrl+X
```

---

## Step 2: Start Services (5 minutes)

### Pull Images

```bash
docker-compose pull
# Downloads latest Docker images (~2-3 GB)
# This may take a few minutes
```

### Start All Containers

```bash
# Start in background
docker-compose up -d

# Monitor startup (watch for "healthy" status)
watch docker-compose ps

# Press Ctrl+C to exit watch
```

### Verify Health

```bash
# Wait 10-15 seconds for services to initialize
sleep 15

# Check all services
docker-compose ps

# Expected output:
# postgres      : healthy
# redis         : healthy
# api-1, api-2  : healthy
# nginx         : healthy
# prometheus    : running
# grafana       : running
# jaeger        : running

# If any are unhealthy, check logs:
docker-compose logs postgres
docker-compose logs api-1
```

---

## Step 3: Verify Installation (5 minutes)

### Test API Health

```bash
# Simple health check
curl http://localhost/health

# Expected response:
# {"status":"healthy","timestamp":"2024-01-06T12:34:56.789Z","instance":"api-instance-1"}

# If this fails: Check docker-compose logs
docker-compose logs nginx
docker-compose logs api-1
```

### Test Authentication

```bash
# Login (get tokens)
curl -X POST http://localhost/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "test-password"
  }' | jq .

# Save the access_token (you'll use it next)
export TOKEN="eyJhbGciOiJIUzI1NiIs..."
```

### Test Query Endpoint

```bash
# Execute a query
curl -X POST http://localhost/api/v1/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the market sentiment?",
    "parameters": {"timeframe": "1d"}
  }' | jq .

# Expected: 200 response with query results
```

---

## Step 4: Access Dashboards (5 minutes)

### Grafana (Metrics Visualization)

```bash
# Open in browser
open http://localhost:3000

# Or use curl
curl http://localhost:3000

# Login
# Username: admin
# Password: admin

# Default dashboards available:
# - System metrics
# - Request latency
# - Error rates
# - Cache performance
```

### Prometheus (Metrics Data)

```bash
# View collected metrics
open http://localhost:9090

# Query examples:
# Rate: rate(group1_rag_api_http_requests_total[5m])
# Latency: histogram_quantile(0.99, http_request_duration_seconds)
# Cache hit rate: cache_hits / (cache_hits + cache_misses)
```

### Jaeger (Distributed Tracing)

```bash
# View request traces
open http://localhost:16686

# Features:
# - Search by service (rag-api)
# - Filter by latency
# - See call traces
# - Identify slow operations
```

---

## Step 5: Basic Operations (8 minutes)

### Scale API Instances

```bash
# Increase to 5 instances
docker-compose up -d --scale api=5

# Verify
docker-compose ps

# Load balancer automatically routes to all instances
for i in {1..10}; do curl http://localhost/health; done
```

### View Logs

```bash
# Tail API logs
docker-compose logs -f api-1 --tail=50

# Tail database logs
docker-compose logs -f postgres --tail=50

# Exit: Ctrl+C
```

### Create Manual Backup

```bash
# Create database backup
python backup_manager.py

# Check S3 (if configured)
aws s3 ls s3://group1-rag-backups/backups/rag/

# Verify backup metadata
psql -U postgres -h localhost -d group1_rag \
  -c "SELECT * FROM backups ORDER BY created_at DESC LIMIT 1;"
```

### Run Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run integration tests
pytest test_enterprise.py -v

# Run specific test
pytest test_enterprise.py::TestLoadBalancing::test_round_robin_distribution -v
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose logs SERVICE_NAME

# Common issues:
# - Port already in use: Change in docker-compose.yml
# - Out of memory: Increase Docker memory limit
# - Permissions: Run with sudo

# Restart everything
docker-compose restart
```

### High Latency

```bash
# Check Prometheus
open http://localhost:9090

# Search: rate(http_request_duration_seconds[5m])

# Check cache hit rate
# High misses = low cache efficiency

# Check database connections
docker-compose exec postgres psql -U postgres -d group1_rag \
  -c "SELECT count(*) FROM pg_stat_activity;"
```

### Container Logs

```bash
# All logs
docker-compose logs

# Specific service
docker-compose logs api-1

# Follow in real-time
docker-compose logs -f

# Last N lines
docker-compose logs --tail=100

# Exit: Ctrl+C
```

### Reset Everything

```bash
# Stop all containers
docker-compose down

# Remove volumes (WARNING: Deletes data)
docker-compose down -v

# Clean up docker
docker system prune -a

# Restart fresh
docker-compose up -d
```

---

## Next Steps

### 1. Production Deployment

For production, switch to Docker Swarm or Kubernetes:

```bash
# Docker Swarm
docker stack deploy -c docker-compose.yml group1-rag

# Kubernetes
python deployment.py  # Generate manifests
kubectl apply -f k8s-manifests.yaml
```

### 2. Configure Secrets

Replace .env secrets with vault:

```bash
# AWS Secrets Manager
aws secretsmanager create-secret --name group1-rag-secrets \
  --secret-string file://secrets.json
```

### 3. Enable HTTPS

Generate SSL certificates:

```bash
# Self-signed (dev only)
openssl req -x509 -newkey rsa:4096 \
  -out cert.pem -keyout key.pem -days 365

# Production: Use Let's Encrypt
# See README.md for certificate automation
```

### 4. Connect External Services

```bash
# RAG retrieval engine
RETRIEVAL_API_URL=http://retrieval-service:8001

# Reasoning engine
REASONING_API_URL=http://reasoning-service:8002

# Update in .env
```

### 5. Setup Continuous Monitoring

```bash
# Enable Slack alerts
SLACK_WEBHOOK_URL=https://hooks.slack.com/...

# Enable PagerDuty
PAGERDUTY_SERVICE_KEY=...

# Test alert
docker-compose exec alertmanager \
  curl -X POST http://localhost:9093/api/v1/alerts
```

---

## Architecture at a Glance

```
┌─────────────────────────────────┐
│    Your Web Browser             │
│    http://localhost             │
└────────────┬────────────────────┘
             │
    ┌────────▼────────┐
    │  Nginx          │ (Load balancer)
    │  Port 80        │
    └────────┬────────┘
             │
    ┌────────▼─────────────┐
    │  API Instances       │ (3+ copies)
    │  Port 8000           │
    └────────┬─────────────┘
             │
    ┌────────┴───────┬──────────┐
    │                │          │
 ┌──▼──┐        ┌──▼──┐    ┌──▼──┐
 │  DB  │        │Cache │   │ Log │
 └──────┘        └──────┘   └─────┘

Monitoring Stack:
- Prometheus (metrics)
- Grafana (dashboards)
- Jaeger (tracing)
- AlertManager (alerts)
```

---

## Performance Baseline

After deployment, you should see:

| Metric | Expected Value |
|--------|---------------|
| Requests/sec | 50-100 (3 instances) |
| P99 Latency | <1000ms |
| Error Rate | <1% |
| Cache Hit Rate | >80% |
| Uptime | >99% |

---

## Common Commands Reference

```bash
# Start/stop
docker-compose up -d           # Start all
docker-compose down            # Stop all
docker-compose restart         # Restart all

# Scale
docker-compose up -d --scale api=5

# Logs
docker-compose logs -f api-1   # Follow logs
docker-compose logs --tail=100 # Last 100 lines

# Database
docker-compose exec postgres psql -U postgres

# Redis
docker-compose exec redis redis-cli

# Status
docker-compose ps              # Container status
docker stats                   # Resource usage

# Clean up
docker-compose down -v         # Remove volumes
docker system prune -a         # Clean all
```

---

## Key URLs

| Service | URL | Username | Password |
|---------|-----|----------|----------|
| API | http://localhost | - | - |
| Grafana | http://localhost:3000 | admin | admin |
| Prometheus | http://localhost:9090 | - | - |
| Jaeger | http://localhost:16686 | - | - |
| Postgres | localhost:5432 | postgres | (from .env) |
| Redis | localhost:6379 | - | - |

---

## Help & Support

```bash
# View all logs
docker-compose logs | grep ERROR

# Specific service health
docker-compose exec api-1 curl http://localhost:8000/health

# Verify database
docker-compose exec postgres pg_isready

# Verify cache
docker-compose exec redis redis-cli ping

# Check metrics
curl http://localhost:9090/api/v1/targets
```

---

## Success Checklist

- [ ] All services running and healthy (`docker-compose ps`)
- [ ] API responds to `/health` endpoint
- [ ] Can login and get JWT token
- [ ] Can execute query endpoint
- [ ] Grafana dashboard loads
- [ ] Prometheus has metrics
- [ ] Jaeger shows traces
- [ ] No ERROR logs in `docker-compose logs`

**If all checked:** Deployment successful! 🎉

---

For detailed information, see [README.md](README.md)
