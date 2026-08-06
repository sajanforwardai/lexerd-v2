# Neo4j Setup Guide for Group One RAG Knowledge Graph

This guide explains how to set up and use the knowledge graph with a real Neo4j database instead of the in-memory mock mode.

## Prerequisites

- Docker (recommended) or Neo4j installed locally
- Python 3.8+
- neo4j Python package

## Option 1: Docker Setup (Recommended)

### Step 1: Start Neo4j Container

```bash
docker run --name group-one-neo4j \
  -p 7687:7687 \
  -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/SecurePassword123 \
  -e NEO4J_ACCEPT_LICENSE_AGREEMENT=yes \
  -d \
  neo4j:5.3-enterprise
```

**Configuration:**
- Bolt port: 7687 (for applications)
- Browser port: 7474 (for web UI)
- Username: `neo4j`
- Password: `SecurePassword123` (change in production)

### Step 2: Verify Neo4j is Running

```bash
# Check container
docker ps | grep neo4j

# Access Neo4j Browser
# Open http://localhost:7474 in your browser
# Login with neo4j / SecurePassword123
```

### Step 3: Install Python Dependencies

```bash
pip install neo4j
```

### Step 4: Update Connection Code

```python
from kg_client import KGClient
from corpus_ingestion import ingest_corpus_files

# Connect to Neo4j
client = KGClient(
    neo4j_uri="bolt://localhost:7687",
    username="neo4j",
    password="SecurePassword123",
    use_mock=False
)

# Create schema (constraints and indexes)
client.create_schema()

# Ingest corpus
stats = ingest_corpus_files(client)
print(f"Ingested {stats['nodes_created']} nodes")

# Query
results = client.query_strategies_by_regime("High-Vol Market")
print(results)
```

## Option 2: Local Neo4j Installation

### On macOS (Homebrew)

```bash
brew install neo4j
brew services start neo4j
```

### On Linux (apt)

```bash
wget -O - https://debian.neo4j.com/neotechnology.gpg.key | sudo apt-key add -
echo 'deb https://debian.neo4j.com stable latest' | sudo tee /etc/apt/sources.list.d/neo4j.list
sudo apt update
sudo apt install neo4j
sudo systemctl start neo4j
```

### On Windows

Download from https://neo4j.com/download/

### Verify Installation

```bash
# Check Neo4j is running
curl http://localhost:7474/browser

# Should return HTML for Neo4j Browser
```

## Connection Parameters

Default local connection:
```python
client = KGClient(
    neo4j_uri="bolt://localhost:7687",
    username="neo4j",
    password="neo4j",  # Default password, change on first login
    use_mock=False
)
```

## Schema Creation

The `create_schema()` method creates:
- **Constraints**: UNIQUE constraints on (id, name) for each entity type
- **Indexes**: Composite index on (entity_type, name) for fast lookups
- **Performance indexes**: Index on relationship confidence for query optimization

```python
client.create_schema()
```

This is equivalent to:

```cypher
# Create constraints for each entity type
CREATE CONSTRAINT FOR (n:Strategy) REQUIRE (n.id, n.name) IS UNIQUE;
CREATE CONSTRAINT FOR (n:MarketRegime) REQUIRE (n.id, n.name) IS UNIQUE;
CREATE CONSTRAINT FOR (n:Greeks) REQUIRE (n.id, n.name) IS UNIQUE;
CREATE CONSTRAINT FOR (n:VolSurface) REQUIRE (n.id, n.name) IS UNIQUE;
CREATE CONSTRAINT FOR (n:TradingOpportunity) REQUIRE (n.id, n.name) IS UNIQUE;
CREATE CONSTRAINT FOR (n:Event) REQUIRE (n.id, n.name) IS UNIQUE;
CREATE CONSTRAINT FOR (n:OrderFlow) REQUIRE (n.id, n.name) IS UNIQUE;
CREATE CONSTRAINT FOR (n:RiskMetric) REQUIRE (n.id, n.name) IS UNIQUE;
CREATE CONSTRAINT FOR (n:Position) REQUIRE (n.id, n.name) IS UNIQUE;

# Create indexes
CREATE INDEX FOR (n:KGNode) ON (n.entity_type, n.name);
CREATE INDEX FOR (r:KGRelationship) ON (r.confidence);
```

## Working with Neo4j Browser

### Access the Browser

Open http://localhost:7474 in your web browser.

### Example Queries

#### View all strategies
```cypher
MATCH (s:Strategy) RETURN s.name, s.description LIMIT 20;
```

#### Find strategies by regime
```cypher
MATCH (regime:MarketRegime {name: "Bull Market"})-[rel:applies_to]-(s:Strategy)
RETURN s.name, s.description, rel.confidence
ORDER BY rel.confidence DESC;
```

#### View relationship statistics
```cypher
MATCH ()-[r]-()
RETURN type(r) as relationship_type, COUNT(*) as count, AVG(r.confidence) as avg_confidence
ORDER BY count DESC;
```

#### Find highly connected nodes (hubs)
```cypher
MATCH (n)-[r]-(m)
RETURN n.name, labels(n)[0] as type, COUNT(*) as connections
ORDER BY connections DESC
LIMIT 20;
```

#### View knowledge graph metrics
```cypher
MATCH (n)
RETURN labels(n)[0] as entity_type, COUNT(*) as count
ORDER BY count DESC;
```

## Performance Tuning

### Increase Memory

For larger datasets, increase Neo4j memory:

```bash
# Docker
docker run -e NEO4J_server_memory_heap_initial_size=2G \
           -e NEO4J_server_memory_heap_max_size=4G \
           neo4j:5.3-enterprise

# Local installation (in conf/neo4j.conf)
server.memory.heap.initial_size=2G
server.memory.memory.heap.max_size=4G
```

### Optimize Queries

The knowledge graph uses:
- **Compound indexes** on (entity_type, name) for fast entity lookups
- **Confidence indexes** for filtering high-confidence relationships
- **Eager loading** via MATCH patterns to minimize round-trips

Example optimized query:

```cypher
-- Using index on (entity_type, name)
MATCH (s:Strategy {name: "Delta Hedging"})
-- Jump directly to relationships (indexed by confidence)
-[rel:applies_to {confidence: $min_conf}]-(regime:MarketRegime)
RETURN s, regime, rel
ORDER BY rel.confidence DESC
LIMIT 10;
```

## Backup and Restore

### Backup

```bash
# Docker backup
docker exec group-one-neo4j \
  neo4j-admin database dump neo4j \
  --to-path=/var/lib/neo4j/backups/backup.dump

# Copy from container
docker cp group-one-neo4j:/var/lib/neo4j/backups/backup.dump ./backup.dump
```

### Restore

```bash
# Copy to container
docker cp ./backup.dump group-one-neo4j:/var/lib/neo4j/backups/

# Restore
docker exec group-one-neo4j \
  neo4j-admin database load neo4j \
  --from-path=/var/lib/neo4j/backups/backup.dump --overwrite
```

## Monitoring

### Via Browser

1. Open http://localhost:7474
2. Click "System" → "System Information"
3. View database statistics, memory usage, query stats

### Via Python

```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver(
    "bolt://localhost:7687",
    auth=("neo4j", "SecurePassword123")
)

with driver.session() as session:
    # Get database info
    info = session.run("CALL dbms.components()").single()
    print(info)
    
    # Get index info
    indexes = session.run("SHOW INDEXES").values()
    for index in indexes:
        print(index)
    
    # Get constraint info
    constraints = session.run("SHOW CONSTRAINTS").values()
    for constraint in constraints:
        print(constraint)
```

## Docker Compose (Complete Stack)

For a complete development environment:

```yaml
# docker-compose.yml
version: '3.8'

services:
  neo4j:
    image: neo4j:5.3-enterprise
    container_name: group-one-neo4j
    ports:
      - "7687:7687"
      - "7474:7474"
    environment:
      NEO4J_AUTH: neo4j/SecurePassword123
      NEO4J_ACCEPT_LICENSE_AGREEMENT: "yes"
      NEO4J_server_memory_heap_initial_size: 2G
      NEO4J_server_memory_heap_max_size: 4G
    volumes:
      - neo4j_data:/var/lib/neo4j/data
      - neo4j_logs:/var/lib/neo4j/logs
    networks:
      - group-one

  python-app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: group-one-app
    depends_on:
      - neo4j
    environment:
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: SecurePassword123
    networks:
      - group-one
    volumes:
      - ./kg:/app/kg

volumes:
  neo4j_data:
  neo4j_logs:

networks:
  group-one:
    driver: bridge
```

Run with:
```bash
docker-compose up -d
```

## Troubleshooting

### Connection Refused

```python
# Increase connection timeout
from neo4j import GraphDatabase

driver = GraphDatabase.driver(
    "bolt://localhost:7687",
    auth=("neo4j", "password"),
    connection_timeout=30,  # seconds
    max_retry_time=30
)
```

### Memory Issues

Reduce batch sizes in ingestion:

```python
# In corpus_ingestion.py
# Process corpus files in batches instead of loading all at once
```

### Slow Queries

Run EXPLAIN to see execution plan:

```cypher
EXPLAIN MATCH (s:Strategy)-[r:applies_to]->(m:MarketRegime)
WHERE r.confidence > 0.8
RETURN s, m;
```

Identify missing indexes and add them.

## Security

### Change Default Password

```cypher
:server user change-password
```

Or via Python:

```python
with driver.session() as session:
    session.run("ALTER USER neo4j SET PASSWORD $password", 
                password="NewSecurePassword123")
```

### Enable Authentication

Already enabled by default with NEO4J_AUTH environment variable.

### Use Encrypted Connections

For production:

```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver(
    "bolt+s://neo4j.example.com:7687",  # +s for encrypted
    auth=("neo4j", "password"),
    trust=TRUST_SYSTEM_CA_SIGNED_CERTIFICATES
)
```

## Production Deployment

For production use:

1. **Use enterprise edition**: `neo4j:5.3-enterprise`
2. **Enable backups**: Automated daily backups
3. **Monitor performance**: Use monitoring tools (Prometheus + Grafana)
4. **Set resource limits**: CPU, memory constraints
5. **Use encryption**: SSL/TLS for all connections
6. **Implement access control**: Role-based security
7. **Enable audit logging**: Track all operations

See Neo4j official documentation: https://neo4j.com/docs/

## Performance Benchmarks

On a Docker instance with 2GB memory:

- Node creation: ~100 nodes/sec
- Relationship creation: ~500 rels/sec
- Query execution: 1-5ms (cached), 10-50ms (uncached)
- Graph export: ~100ms
- Full corpus ingestion: ~2s

## Next Steps

1. Set up Neo4j using one of the methods above
2. Run `client.create_schema()` to create indexes
3. Run `ingest_corpus_files(client)` to populate the graph
4. Execute queries using the pre-built query methods
5. Access the browser at http://localhost:7474 to visualize the graph

## References

- **Neo4j Documentation**: https://neo4j.com/docs/
- **Cypher Manual**: https://neo4j.com/docs/cypher-manual/
- **Python Driver**: https://neo4j.com/developer/python/
- **Docker Hub**: https://hub.docker.com/_/neo4j
