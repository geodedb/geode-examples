# Large-Scale Performance Testing Guide

This guide covers deploying Geode for extensive performance testing with extremely large graphs.

## Claimed Maximums (from geodedb.com)

| Metric | Claimed Value | Test Required |
|--------|---------------|---------------|
| Node Count | 100M+ nodes | Full data volume test |
| Relationship Count | 1B+ relationships | Graph density test |
| Concurrent Connections | 10,000+ | Connection scaling test |
| Read-Only Throughput | 100,000 txn/sec | Throughput benchmark |
| Read-Write Throughput | 10,000-50,000 txn/sec | Mixed workload test |

## Hardware Requirements

### Minimum for Large-Scale Testing (1M-10M nodes)

| Component | Specification |
|-----------|---------------|
| CPU | 8+ cores (prefer 16+) |
| RAM | 32GB minimum, 64GB recommended |
| Storage | 500GB NVMe SSD |
| Network | 10Gbps for multi-node |

### Recommended for Extreme Testing (100M+ nodes)

| Component | Specification |
|-----------|---------------|
| CPU | 32+ cores |
| RAM | 256GB+ |
| Storage | 2TB+ NVMe SSD (prefer RAID 0) |
| Network | 25Gbps+ |

### Storage Estimation

Based on the scalability config metrics (~1KB per node):

| Nodes | Relationships | Estimated Storage |
|-------|---------------|-------------------|
| 1M | 5M | ~10GB |
| 10M | 50M | ~100GB |
| 100M | 500M | ~1TB |
| 100M | 1B | ~2TB |

## Deployment Options

### Option 1: Docker Compose (Single Server)

Best for: Development, testing up to 10M nodes

```bash
# Start Geode with production settings
docker compose -f docker/docker-compose.production.yml up -d

# Monitor logs
docker compose -f docker/docker-compose.production.yml logs -f geode
```

### Option 2: Kubernetes with Helm (Production Scale)

Best for: Multi-node clusters, 100M+ nodes testing

```bash
# Add Geode Helm repository (when available)
# helm repo add geode https://charts.geodedb.com

# Install with production values
helm install geode ./helm/geode \
  -f ./helm/geode/values.production.yaml \
  --namespace geode \
  --create-namespace

# For extreme scale testing
helm install geode ./helm/geode \
  -f ./helm/geode/values.extreme.yaml \
  --namespace geode \
  --create-namespace
```

### Option 3: Bare Metal / VM (Maximum Performance)

Best for: Maximum throughput testing, benchmarking

```bash
# Run the server setup script
./scripts/setup_production_server.sh

# Or manually:
./geode serve \
  --data-dir /data/geode \
  --listen 0.0.0.0:3141 \
  --log-level info \
  --page-cache-size 64GB \
  --max-connections 10000
```

## Deployment Profiles

### Profile: Standard (CI/CD)

- **Nodes**: 100,000
- **Relationships**: 500,000
- **Connections**: 100
- **Duration**: 5 minutes
- **Use Case**: Regular CI/CD validation

```bash
make benchmark-standard
```

### Profile: Full (Release Validation)

- **Nodes**: 1,000,000
- **Relationships**: 5,000,000
- **Connections**: 1,000
- **Duration**: 30 minutes
- **Use Case**: Pre-release testing

```bash
make benchmark-full
```

### Profile: Extreme (Claim Verification)

- **Nodes**: 100,000,000
- **Relationships**: 1,000,000,000
- **Connections**: 10,000
- **Duration**: 24+ hours
- **Use Case**: Maximum scale verification

```bash
make benchmark-extreme
```

## Running Large-Scale Tests

### Step 1: Deploy Geode Server

```bash
# For Docker (single node)
docker compose -f docker/docker-compose.production.yml up -d

# Verify server is healthy
docker compose -f docker/docker-compose.production.yml exec geode \
  geode query --server localhost:3141 --insecure "RETURN 1"
```

### Step 2: Generate Test Data

```bash
# Generate extreme-scale test data (adjust parameters as needed)
python benchmarks/data-generators/scale_test.py \
  --nodes 1000000 \
  --rels-per-node 5 \
  --batch-size 10000 \
  --output reports/scale_data.json

# For 100M nodes (requires significant time and resources)
python benchmarks/data-generators/scale_test.py \
  --nodes 100000000 \
  --rels-per-node 10 \
  --batch-size 50000 \
  --output reports/extreme_scale_data.json
```

### Step 3: Run Benchmarks

```bash
# Read-only throughput (verify 100K txn/sec claim)
python benchmarks/load-tests/read_only.py \
  --workers 100 \
  --duration 300 \
  --output reports/perf-read-extreme.json

# Mixed workload (verify 10K-50K txn/sec claim)
python benchmarks/load-tests/read_write.py \
  --workers 50 \
  --duration 300 \
  --read-ratio 0.7 \
  --output reports/perf-rw-extreme.json

# Concurrent connections (verify 10K+ connections claim)
python benchmarks/load-tests/concurrent_connections.py \
  --target 10000 \
  --batch-size 500 \
  --output reports/perf-connections.json
```

### Step 4: Monitor and Collect Metrics

```bash
# Enable monitoring stack
docker compose -f docker/docker-compose.production.yml --profile monitoring up -d

# Prometheus metrics available at http://localhost:9091
# Grafana dashboard at http://localhost:3000 (admin/geode)

# Export metrics during test
curl -s http://localhost:9090/metrics > reports/metrics_snapshot.txt
```

## Native Client Testing

The subprocess-based benchmarks have ~400ms overhead per query. For accurate throughput testing, use native clients:

### Go Client Benchmark

```bash
cd ../geode-client-go
go run examples/benchmark/main.go \
  --host localhost:3141 \
  --workers 100 \
  --duration 60s
```

### Rust Client Benchmark

```bash
cd ../geode-client-rust
cargo run --release --example benchmark -- \
  --host localhost:3141 \
  --workers 100 \
  --duration 60
```

### Python Async Client

```bash
cd ../geode-client-python
python examples/benchmark.py \
  --host localhost:3141 \
  --workers 100 \
  --duration 60
```

## Kubernetes Deployment for Extreme Scale

### Prerequisites

1. Kubernetes cluster with 3+ nodes
2. Each node: 32+ cores, 128GB+ RAM, NVMe storage
3. Storage class with fast SSDs
4. Helm 3.x installed

### Deploy with Extreme Values

```bash
helm install geode ./helm/geode \
  -f ./helm/geode/values.extreme.yaml \
  --set persistence.size=2Ti \
  --set walPersistence.size=500Gi \
  --set config.storage.pageCacheSize=64GB \
  --namespace geode
```

### Monitor Cluster

```bash
# Check pod status
kubectl get pods -n geode -w

# View logs
kubectl logs -n geode -l app.kubernetes.io/name=geode -f

# Check metrics
kubectl port-forward -n geode svc/geode 9090:9090
curl localhost:9090/metrics
```

## Troubleshooting

### Out of Memory

Increase page cache size proportionally to data:
- 1M nodes: 2GB cache
- 10M nodes: 16GB cache
- 100M nodes: 64GB+ cache

### Slow Writes

1. Increase WAL buffer: `--wal-buffer-size 128MB`
2. Use faster storage (NVMe)
3. Decrease WAL sync interval for writes: `--wal-sync-interval 10ms`

### Connection Limits

Increase system limits:
```bash
# /etc/security/limits.conf
* soft nofile 100000
* hard nofile 100000

# /etc/sysctl.conf
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
```

### Storage Performance

Test storage before benchmarking:
```bash
# Test sequential write
fio --name=seqwrite --rw=write --bs=1M --size=10G --numjobs=4 --direct=1

# Test random read (important for graph traversal)
fio --name=randread --rw=randread --bs=4K --size=10G --numjobs=4 --direct=1
```

## Expected Results

| Test | Subprocess Baseline | Native Client Expected |
|------|---------------------|------------------------|
| Read throughput | ~2-5 qps | 50,000-100,000 qps |
| Write throughput | ~1-3 qps | 10,000-50,000 qps |
| P99 latency | ~500ms | <10ms |
| Max connections | Limited by OS | 10,000+ |

Note: Subprocess-based testing provides functional verification. For throughput verification, use native clients.

## Next Steps

1. Deploy server using your preferred method
2. Run smoke tests to verify connectivity
3. Generate test data at target scale
4. Execute benchmarks with monitoring
5. Collect and analyze results
6. Compare against claimed maximums
