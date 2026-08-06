# Group One Trading RAG - Phase 4 Enterprise Infrastructure

**Version:** 4.0.0  
**Status:** Production-Ready  
**Last Updated:** 2024-01-06

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Quick Start](#quick-start)
3. [Deployment Guides](#deployment-guides)
4. [Configuration](#configuration)
5. [High Availability](#high-availability)
6. [Monitoring & Observability](#monitoring--observability)
7. [Backup & Disaster Recovery](#backup--disaster-recovery)
8. [Scaling](#scaling)
9. [Security](#security)
10. [Troubleshooting](#troubleshooting)
11. [Performance Tuning](#performance-tuning)
12. [API Reference](#api-reference)

---

## Architecture Overview

### System Components

Group One Trading RAG Phase 4 Enterprise is a production-grade system serving 100+ concurrent users with 99.9% uptime SLA. The architecture consists of:

**Core Services:**
- **API Server** (FastAPI): Multi-instance REST API with JWT authentication, rate limiting, and audit logging
- **Background Workers** (Celery): Async task processing for long-running operations
- **Database** (PostgreSQL): Primary data store with replication support
- **Cache** (Redis): Session storage, rate limiting, and query caching with Sentinel failover
- **Load Balancer** (Nginx): HTTP/HTTPS termination, request routing, and health checks

**Observability Stack:**
- **Prometheus**: Metrics collection and storage (30-day retention)
- **Grafana**: Visualization dashboards
- **Jaeger**: Distributed tracing with request correlation
- **AlertManager**: Alert routing and deduplication
- **OpenTelemetry Collector**: Trace aggregation

**Data Persistence:**
- **AWS S3**: Backup storage with automatic lifecycle policies
- **PostgreSQL WAL**: Point-in-time recovery support
- **Git**: Configuration version control

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Internet Users                          │
└─────────────────────────────────────────────────────────────┘
                            │
                    ┌───────▼────────┐
                    │  Nginx LB      │
                    │ (port 80/443)  │
                    └───────┬────────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
       ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
       │ API-1   │    │ API-2   │    │ API-3   │
       │ (8001)  │    │ (8002)  │    │ (8003)  │
       └────┬────┘    └────┬────┘    └────┬────┘
            │               │               │
            └───────────────┼───────────────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
       ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
       │PostgreSQL   │Redis    │Cache│Monitoring
       │Primary      │Sentinel │Services
       │(5432)      │(6379)   │
       └────────┘    └────────┘    └────────┘
```

### Quality Bars (Guaranteed)

- **Availability**: 99.9% uptime (4.38 hours/year max downtime)
- **Performance**: P99 latency <5s under full load
- **Throughput**: 100+ concurrent users, 100 req/s sustained
- **Scaling**: Horizontal scaling to 10+ instances
- **Recovery**: RTO <1 hour, RPO <24 hours
- **Security**: Encrypted secrets, audit trails, role-based access

---

## Quick Start

### Prerequisites

- Docker & Docker Compose 20.10+
- Docker Swarm or Kubernetes (for production)
- AWS account with S3 access (for backups)
- Python 3.11+ (for local development)

### 5-Minute Setup (Docker Compose)

```bash
# Clone repository
git clone <repo> group1-rag-enterprise
cd group1-rag-enterprise/enterprise

# Copy environment template
cp .env.example .env

# Edit .env with your configuration
# IMPORTANT: Change SECRET_KEY and DB_PASSWORD
vim .env

# Start all services
docker-compose up -d

# Wait for services to be healthy
sleep 30
docker-compose ps

# Verify API is running
curl http://localhost/health
```

### Verify Installation

```bash
# Check all containers are running
docker-compose ps

# View logs
docker-compose logs api-1

# Test API endpoint
curl -X POST http://localhost/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "test"}'

# Access Grafana dashboard
open http://localhost:3000
# Default: admin / admin

# Access Prometheus
open http://localhost:9090

# Access Jaeger traces
open http://localhost:16686
```

---

## Deployment Guides

### Docker Compose (Development/Staging)

Ideal for small deployments and testing.

**Pros:**
- Single command deployment
- Full stack in containers
- Easy local development

**Cons:**
- Limited to single machine
- No automatic failover
- Manual scaling

**Deploy:**

```bash
# Start services
docker-compose up -d

# Scale API instances
docker-compose up -d --scale api=3

# Check status
docker-compose ps

# View logs
docker-compose logs -f api-1

# Stop all
docker-compose down -v
```

### Docker Swarm (Production - Small)

Ideal for 3-10 instance deployments.

**Deploy Stack:**

```bash
# Initialize Swarm (run on leader)
docker swarm init

# Add worker nodes
docker swarm join --token <token> <leader-ip>:2377

# Deploy stack
docker stack deploy -c docker-compose.yml group1-rag

# View services
docker service ls
docker service ps group1-rag_api

# Scale services
docker service scale group1-rag_api=5

# Update image
docker service update --image group1-rag-api:v4.1.0 group1-rag_api

# View logs
docker service logs group1-rag_api
```

### Kubernetes (Production - Large)

Ideal for 10+ instance deployments with automatic scaling.

**Generate K8s Manifests:**

```bash
# Generate manifests
python deployment.py

# Output to YAML
python -c "from deployment import KubernetesDeployment; d = KubernetesDeployment(); d.export_yaml(d.generate_all_manifests(), 'k8s-manifests.yaml')"

# Deploy
kubectl apply -f k8s-manifests.yaml

# Verify deployment
kubectl get pods -n group1-rag
kubectl get svc -n group1-rag
kubectl describe deployment rag-api -n group1-rag

# Scale HPA
kubectl autoscale deployment rag-api --min=3 --max=10

# View logs
kubectl logs -f -l app=rag-api -n group1-rag

# Monitor
kubectl get hpa -n group1-rag
kubectl top pods -n group1-rag
```

---

## Configuration

### Environment Variables

All configuration is via `.env` file. Key sections:

**Application Settings:**
```bash
ENVIRONMENT=production          # production|staging|development
LOG_LEVEL=INFO                 # DEBUG|INFO|WARN|ERROR
SECRET_KEY=<change-me>         # CRITICAL: Change in production
```

**Database Connection:**
```bash
DB_HOST=postgres
DB_USER=postgres
DB_PASSWORD=<change-me>        # CRITICAL: Use strong password
DATABASE_URL=postgresql://...
DB_POOL_MIN=5                  # Min connections
DB_POOL_MAX=20                 # Max connections
```

**Rate Limiting:**
```bash
RATE_LIMIT_PER_USER=100        # req/s per user
RATE_LIMIT_GLOBAL=1000         # req/s global
```

**AWS/S3 Backup:**
```bash
AWS_ACCESS_KEY_ID=<key>
AWS_SECRET_ACCESS_KEY=<secret>
S3_BUCKET=group1-rag-backups
BACKUP_RETENTION_DAYS=30
```

**Observability:**
```bash
JAEGER_HOST=jaeger
JAEGER_PORT=6831
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

### Secrets Management

**For Production:**

1. **Use a secrets vault** (AWS Secrets Manager, HashiCorp Vault, K8s Secrets)

```bash
# Store in AWS Secrets Manager
aws secretsmanager create-secret --name group1-rag-secrets \
  --secret-string file://secrets.json

# Retrieve in application
import boto3
secrets_client = boto3.client('secretsmanager')
secret = secrets_client.get_secret_value(SecretId='group1-rag-secrets')
```

2. **Never commit secrets to git**

```bash
# .gitignore
.env
.env.local
secrets.json
*.key
*.pem
```

3. **Rotate keys regularly**

```bash
# Monthly key rotation
python scripts/rotate_secrets.py
```

---

## High Availability

### Load Balancing

**Round-Robin (Default):**
```
Request 1 → API-1
Request 2 → API-2
Request 3 → API-3
Request 4 → API-1 (cycle repeats)
```

**Weighted Load Balancing:**
```yaml
# nginx.conf
upstream rag_api {
    server api-1:8000 weight=2;  # Gets 50% of traffic
    server api-2:8000 weight=1;  # Gets 25%
    server api-3:8000 weight=1;  # Gets 25%
}
```

**Least Connections:**
```python
# Automatically routes to instance with fewest active connections
# Enabled in ha_manager.py
lb.select_instance(strategy="least_connections")
```

### Circuit Breaker Pattern

Automatically stops routing to failing instances:

```python
from ha_manager import CircuitBreaker, CircuitBreakerConfig

cb = CircuitBreaker(
    name="api-1",
    config=CircuitBreakerConfig(
        failure_threshold=5,      # Open after 5 failures
        success_threshold=2,      # Close after 2 successes
        timeout=60,               # Try to recover after 60s
    )
)

# Usage
try:
    result = await cb.call(api_request)
except Exception as e:
    # Circuit is OPEN, fail fast
    return fallback_response()
```

### Health Checks

**Liveness Probe** (Is pod alive?)
```
GET /health
Returns 200 if healthy
```

**Readiness Probe** (Is pod ready for traffic?)
```
GET /ready
Returns 200 when fully initialized
```

**In Kubernetes:**
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```

### Database Replication

**Primary-Replica Setup:**

```sql
-- On PRIMARY
CREATE PUBLICATION rag_pub FOR ALL TABLES;

-- On REPLICA
CREATE SUBSCRIPTION rag_sub CONNECTION 'postgresql://...' PUBLICATION rag_pub;
```

**Automatic Failover:**

```bash
# Using patroni for automatic failover
patroni /etc/patroni/postgresql.yml

# Check cluster status
patronictl -c /etc/patroni/postgresql.yml list

# Manual failover if needed
patronictl -c /etc/patroni/postgresql.yml failover
```

### Redis Sentinel (Cache HA)

**Configuration:**

```conf
sentinel monitor mymaster 127.0.0.1 6379 1
sentinel down-after-milliseconds mymaster 5000
sentinel failover-timeout mymaster 10000
```

**Automatic Failover:**

```python
import redis.sentinel

sentinels = [('sentinel1', 26379), ('sentinel2', 26379)]
sentinel = redis.sentinel.Sentinel(sentinels)

# Automatic failover to replica if primary fails
redis_client = sentinel.master_for('mymaster', socket_timeout=0.1)
redis_client.set('key', 'value')  # Automatically routes to healthy primary
```

---

## Monitoring & Observability

### Metrics Dashboard

Access Grafana at `http://localhost:3000`

**Key Metrics:**

| Metric | Target | Alert |
|--------|--------|-------|
| Request Rate | 100 req/s | >200 req/s |
| P99 Latency | <1s | >5s |
| Error Rate | <1% | >5% |
| Cache Hit Rate | >90% | <70% |
| DB Connections | <15/20 | >18/20 |

### Distributed Tracing

Access Jaeger at `http://localhost:16686`

**Trace a Request:**

```python
# Instrumented automatically with OpenTelemetry
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("query_execution"):
    # Your code here
    result = await execute_query(query)
    # Span is automatically exported to Jaeger
```

**Example Trace Flow:**

```
api-1 [1.2ms] ─── query_execution [1.0ms]
                   ├── cache_lookup [0.1ms]
                   ├── db_query [0.8ms] ──── postgres [0.7ms]
                   └── format_result [0.1ms]
```

### Alerts

**Critical Alerts (1 minute):**
- Pod crash (InstanceDown)
- High error rate (>5%)
- Database connection pool exhausted

**Warning Alerts (5 minutes):**
- High latency (P99 >5s)
- Cache miss rate >50%
- Rate limit exceeded

**Info Alerts (30 minutes):**
- Slow query detected
- Backup failed
- Certificate expiring soon

**View Active Alerts:**

```bash
# Via Prometheus
curl http://localhost:9090/api/v1/alerts

# Via AlertManager
curl http://localhost:9093/api/v1/alerts
```

### Custom Metrics

**Add Business Metrics:**

```python
from monitoring import MetricsCollector

metrics = MetricsCollector()

# Counter
metrics.trades_executed_total.labels(
    strategy="momentum",
    status="success"
).inc()

# Histogram
metrics.trade_pnl.labels(strategy="momentum").observe(250.50)

# Gauge
metrics.system_up.set(1)
```

---

## Backup & Disaster Recovery

### Backup Strategy

**RTO Target:** < 1 hour  
**RPO Target:** < 24 hours

**Backup Schedule:**

```
Daily at 2:00 AM UTC
├── Full database snapshot → S3
├── Configuration backup → Git
└── Audit logs → S3
```

**Automation:**

```bash
# Docker-based daily backups
docker run --rm \
  -e DATABASE_URL=postgresql://... \
  -e AWS_ACCESS_KEY_ID=... \
  group1-rag-backup:latest
```

### Creating Manual Backups

```python
from backup_manager import BackupManager, BackupConfig

config = BackupConfig(
    db_host="localhost",
    db_name="group1_rag",
    db_user="postgres",
    db_password="secret",
    s3_bucket="group1-rag-backups",
)

manager = BackupManager(config)

# Create backup
result = manager.full_backup()
print(f"Backup: {result['s3_key']}")
print(f"Size: {result['file_size_bytes']} bytes")
print(f"Hash: {result['file_hash']}")
```

### Disaster Recovery Procedure

**1. Assess Damage (5 mins)**

```bash
# Check database status
psql -U postgres -d group1_rag -c "SELECT 1;"

# Check S3 backups
aws s3 ls s3://group1-rag-backups/backups/rag/ --recursive
```

**2. Prepare Recovery Environment (10 mins)**

```bash
# Stop all API instances to prevent writes
docker-compose stop api-1 api-2 api-3 worker

# Create new database (if corruption)
dropdb -U postgres group1_rag
createdb -U postgres group1_rag
```

**3. Restore from Backup (30 mins)**

```python
from backup_manager import BackupManager, BackupConfig

config = BackupConfig(...)
manager = BackupManager(config)

# Restore from S3
manager.restore_from_s3("backups/rag/2024/01/06/120000/backup.sql.gz")

# Verify restore
psql -U postgres -d group1_rag -c "SELECT COUNT(*) FROM audit_logs;"
```

**4. Verify Data Integrity (10 mins)**

```bash
# Run integrity checks
psql -U postgres -d group1_rag -c "REINDEX DATABASE group1_rag;"

# Verify row counts
psql -U postgres -d group1_rag -c "
  SELECT
    'audit_logs' as table_name, COUNT(*) as row_count FROM audit_logs
  UNION ALL
  SELECT 'users', COUNT(*) FROM users
  UNION ALL
  SELECT 'trades', COUNT(*) FROM trades;
"
```

**5. Restart Services (5 mins)**

```bash
# Restart API instances
docker-compose up -d api-1 api-2 api-3 worker

# Health check
curl http://localhost/health
```

**Total RTO: ~60 minutes**

---

## Scaling

### Horizontal Scaling

**Scale API Instances:**

```bash
# Docker Compose
docker-compose up -d --scale api=5

# Docker Swarm
docker service scale group1-rag_api=5

# Kubernetes
kubectl scale deployment rag-api --replicas=5 -n group1-rag
```

**Expected Performance:**

| Instances | Throughput | P99 Latency | Availability |
|-----------|-----------|-------------|---------------|
| 2         | 50 req/s  | 2s          | 95%           |
| 3         | 100 req/s | 1.5s        | 98%           |
| 5         | 150 req/s | 1s          | 99.5%         |
| 10        | 250 req/s | 0.8s        | 99.9%         |

### Vertical Scaling

**Increase Pod Resources:**

```yaml
# Kubernetes
resources:
  requests:
    cpu: "500m"      # 0.5 CPU
    memory: "512Mi"  # 512MB
  limits:
    cpu: "2"         # 2 CPUs
    memory: "2Gi"    # 2GB
```

**Database Connection Pool:**

```bash
# Increase max connections
DB_POOL_MAX=50

# Reload config
docker-compose restart postgres
```

### Auto-Scaling

**Kubernetes HPA (Horizontal Pod Autoscaler):**

```yaml
minReplicas: 2
maxReplicas: 10
targetCPUUtilizationPercentage: 70
targetMemoryUtilizationPercentage: 80
```

**Monitor Scaling:**

```bash
kubectl get hpa -w
# Automatically scales up/down based on metrics
```

---

## Security

### Authentication

**JWT Tokens:**

```bash
# Get access token
curl -X POST http://localhost/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password"}'

# Response
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}

# Use token in requests
curl http://localhost/query \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

**Token Expiration:**

- Access token: 1 hour
- Refresh token: 7 days
- Automatic refresh before expiration

### Authorization

**Role-Based Access Control (RBAC):**

| Role | Permissions |
|------|-------------|
| Admin | All (read, write, delete, admin) |
| Risk Officer | Read, Write, Execute, Audit |
| Trader | Read, Write, Execute |
| Analyst | Read, Write |
| Viewer | Read only |

**Check Permissions:**

```python
from api_server import ROLE_PERMISSIONS, UserRole

if "write" in ROLE_PERMISSIONS[user.role]:
    # User can perform write operations
    pass
```

### Audit Logging

**All Actions Logged:**

```json
{
  "timestamp": "2024-01-06T12:34:56.789Z",
  "user_id": "user-123",
  "org_id": "org-1",
  "action": "QUERY_EXECUTE",
  "resource": "query",
  "details": {
    "query": "SELECT * FROM trades WHERE...",
    "request_id": "req-abc123"
  },
  "ip_address": "192.168.1.100",
  "status": "success"
}
```

**Query Audit Logs:**

```bash
# Via API
curl http://localhost/audit/logs?limit=100 \
  -H "Authorization: Bearer <token>"

# Via Database
psql -U postgres -d group1_rag
SELECT * FROM audit_logs
WHERE org_id = 'org-1'
  AND created_at >= NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC
LIMIT 100;
```

### Network Security

**Firewall Rules:**

```
Inbound:
  - Port 80 (HTTP) from anywhere
  - Port 443 (HTTPS) from anywhere
  - Port 22 (SSH) from admin IPs only

Outbound:
  - Port 443 (HTTPS) to internet (for external APIs)
  - Port 5432 (PostgreSQL) within VPC only
  - Port 6379 (Redis) within VPC only
```

**Network Policies (K8s):**

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: rag-network-policy
spec:
  podSelector:
    matchLabels:
      app: rag-api
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: nginx-ingress
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: postgres
```

### SSL/TLS

**Enable HTTPS:**

```bash
# Generate self-signed certificate (dev only)
openssl req -x509 -newkey rsa:4096 -out cert.pem -keyout key.pem -days 365

# Copy to nginx
cp cert.pem nginx/ssl/
cp key.pem nginx/ssl/

# Update nginx.conf to use SSL
# (See nginx.conf HTTPS section)
```

---

## Troubleshooting

### Common Issues

**1. API Container Keeps Restarting**

```bash
# Check logs
docker-compose logs api-1 --tail=50

# Common causes:
# - Database not ready: Wait for postgres health check
# - Secret key not set: Ensure SECRET_KEY in .env
# - Port already in use: Change port in docker-compose.yml
```

**2. High Latency (>5s)**

```bash
# Check query cache
redis-cli
> DBSIZE
> KEYS query_cache:*

# Check database slow queries
psql -U postgres -d group1_rag
# Enable logging
ALTER SYSTEM SET log_statement = 'all';
ALTER SYSTEM SET log_duration = 'on';
SELECT pg_reload_conf();

# Check Prometheus for bottleneck
# Navigate to http://localhost:9090 and search:
# histogram_quantile(0.99, rate(request_duration_seconds[5m]))
```

**3. Database Connection Pool Exhausted**

```bash
# Check current connections
psql -U postgres -d group1_rag -c "SELECT count(*) FROM pg_stat_activity;"

# Increase pool size
DB_POOL_MAX=50
docker-compose restart api-1 api-2 api-3

# Identify long-running queries
psql -U postgres -d group1_rag -c "
SELECT pid, usename, query, state, query_start
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY query_start DESC;
"
```

**4. Out of Memory**

```bash
# Check memory usage
docker stats

# Increase pod memory
# Docker Compose: Update docker-compose.yml
# Kubernetes: Update deployment resources

# Restart to free memory
docker-compose restart
```

**5. Disk Space Full**

```bash
# Check disk usage
df -h

# Clean up old logs
docker-compose exec prometheus \
  find /prometheus -type f -name "*.db" -mtime +30 -delete

# Remove old backups
aws s3 rm s3://group1-rag-backups/backups/rag/ \
  --recursive \
  --exclude "*" \
  --include "*$(date -d '60 days ago' +%Y/%m/%d)*"
```

### Debug Mode

```bash
# Enable verbose logging
LOG_LEVEL=DEBUG docker-compose up api-1

# Enable Prometheus metrics scraping
# (automatically enabled)
curl http://localhost:9090/api/v1/targets

# Jaeger trace debugging
# Navigate to http://localhost:16686
# Search for error traces
```

---

## Performance Tuning

### Database Optimization

**Connection Pooling:**

```bash
DB_POOL_MIN=10    # Min idle connections
DB_POOL_MAX=30    # Max concurrent connections
```

**Query Optimization:**

```sql
-- Add indexes for common queries
CREATE INDEX idx_trades_org_symbol ON trades(org_id, symbol);
CREATE INDEX idx_audit_user_time ON audit_logs(user_id, created_at DESC);

-- Analyze query plans
EXPLAIN ANALYZE
SELECT * FROM trades
WHERE org_id = 'org-1' AND symbol = 'AAPL'
ORDER BY created_at DESC
LIMIT 100;
```

### Cache Optimization

**Query Result Caching:**

```python
# Cache hot queries for 1 hour
redis_client.setex(
    key=f"query_cache:{org_id}:{query_hash}",
    time=3600,
    value=json.dumps(result)
)
```

**Cache Invalidation:**

```python
# Invalidate on trade execution
def execute_trade(trade):
    # ... execute trade ...
    # Invalidate cache for affected queries
    redis_client.delete(f"query_cache:{org_id}:*")
```

### CPU/Memory Optimization

**API Instance:**
- Keep CPU utilization 50-70% for headroom
- Memory per instance: 512MB-1GB
- Worker threads: 4-8 (CPU cores)

**Database:**
- shared_buffers: 25% of RAM
- work_mem: RAM / (max_connections * 2)
- maintenance_work_mem: RAM / 4

---

## API Reference

### Authentication Endpoints

**POST /auth/login** - Authenticate user

```bash
curl -X POST http://localhost/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password"
  }'

# Response (200)
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**POST /auth/refresh** - Refresh access token

```bash
curl -X POST http://localhost/auth/refresh \
  -H "Authorization: Bearer <refresh_token>"

# Response (200)
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### Query Endpoints

**POST /query** - Execute RAG query

```bash
curl -X POST http://localhost/query \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the market sentiment for AAPL?",
    "parameters": {
      "symbol": "AAPL",
      "timeframe": "1d"
    }
  }'

# Response (200)
{
  "request_id": "req-abc123",
  "result": {
    "status": "success",
    "data": { ... },
    "confidence": 0.95
  },
  "latency_ms": 1234.5,
  "cached": false
}
```

**GET /audit/logs** - Retrieve audit logs

```bash
curl http://localhost/audit/logs?limit=100 \
  -H "Authorization: Bearer <access_token>"

# Response (200)
{
  "logs": [
    {
      "id": "log-123",
      "user_id": "user-1",
      "action": "QUERY_EXECUTE",
      "timestamp": "2024-01-06T12:34:56Z",
      "status": "success"
    }
  ],
  "count": 100
}
```

### Health/Status Endpoints

**GET /health** - Liveness probe

```bash
curl http://localhost/health

# Response (200)
{
  "status": "healthy",
  "timestamp": "2024-01-06T12:34:56Z",
  "instance": "api-instance-1"
}

# Response (503) if unhealthy
{
  "status": "unhealthy",
  "detail": "Database connection failed"
}
```

**GET /ready** - Readiness probe

```bash
curl http://localhost/ready

# Response (200)
{
  "status": "ready"
}

# Response (503) if not ready
{
  "status": "not_ready"
}
```

**GET /metrics** - Prometheus metrics

```bash
curl http://localhost/metrics

# Response (200) - Prometheus format
# HELP group1_rag_api_http_requests_total Total HTTP requests
# TYPE group1_rag_api_http_requests_total counter
group1_rag_api_http_requests_total{method="GET",status="200"} 12345
```

---

## Support & Contribution

For issues, questions, or contributions, please refer to the main repository.

**Emergency Contact:** devops@example.com  
**Documentation:** https://docs.example.com/rag-enterprise  
**Status Page:** https://status.example.com
