# Benchmarks

Performance benchmarks for verifying Geode's documented performance claims.

## Claims Being Verified

| Claim | Source | Test |
|-------|--------|------|
| Read-only: up to 100,000 txn/sec | Performance Guide | `load-tests/read_only.py` |
| Read-write: 10,000-50,000 txn/sec | Performance Guide | `load-tests/read_write.py` |
| Write-heavy: 5,000-20,000 txn/sec | Performance Guide | `load-tests/write_heavy.py` |
| Vector distance: <50ns (8D L2) | Features Overview | `load-tests/vector_distance.py` |
| 10,000+ concurrent connections | Performance Guide | `load-tests/concurrent_connections.py` |
| Memory-mapped I/O: 13.18x improvement | Features Overview | (via verification tests) |

## Directory Structure

```
benchmarks/
├── config/                      # Benchmark configurations
│   ├── throughput.yaml          # Throughput benchmark settings
│   ├── latency.yaml             # Latency benchmark settings
│   └── scalability.yaml         # Scalability test settings
├── load-tests/                  # Load testing scripts
│   ├── read_only.py             # Read-only throughput benchmark
│   ├── read_write.py            # Mixed read/write benchmark
│   ├── write_heavy.py           # Write-heavy benchmark
│   ├── concurrent_connections.py # Connection scaling benchmark
│   ├── vector_distance.py       # Vector operation latency
│   ├── multi_client_benchmark.py # Multi-client native benchmark orchestrator
│   └── native_client_benchmark.py # Python native client benchmark
├── data-generators/             # Test data generators
│   ├── social_graph.py          # Social network data
│   ├── knowledge_graph.py       # Knowledge graph data
│   └── scale_test.py            # Large-scale test data
├── results/                     # Benchmark results (gitignored)
└── requirements.txt             # Python dependencies
```

## Prerequisites

```bash
pip install -r requirements.txt
```

## Running Benchmarks

### Native Client Benchmarks (Recommended)

For true high-throughput benchmarks using persistent QUIC connections, use the native client benchmarks. These use actual native client libraries for each language rather than spawning subprocesses.

```bash
# Run all available native clients
python load-tests/multi_client_benchmark.py --clients all --workers 10 --queries 1000

# Run specific clients
python load-tests/multi_client_benchmark.py --clients go,rust --workers 20 --queries 5000

# Python only (native aioquic client)
python load-tests/native_client_benchmark.py --workers 10 --queries 1000
```

**Available Native Clients:**

| Client | Location | Direct Run Command |
|--------|----------|-------------------|
| Go | `geode-client-go/cmd/benchmark/` | `go run ./cmd/benchmark --workers 10 --queries 1000 --json` |
| Python | `load-tests/native_client_benchmark.py` | `python native_client_benchmark.py --workers 10 --queries 1000 --json` |
| Rust | `geode-client-rust/examples/benchmark.rs` | `cargo run --release --example benchmark -- --workers 10 --queries 1000 --json` |
| Node.js | `geode-client-nodejs/benchmarks/benchmark.ts` | `npx tsx benchmarks/benchmark.ts --workers 10 --queries 1000 --json` |
| Zig | `geode-client-zig/benchmark.zig` | `zig build benchmark -- --workers 10 --queries 1000 --json` |

All native benchmarks:
- Use persistent QUIC connections (no subprocess overhead)
- Support `--json` flag for machine-readable output
- Calculate p50, p95, p99, avg latency and throughput QPS
- Use consistent status thresholds: EXCELLENT (≥10k qps), GOOD (≥1k), ACCEPTABLE (≥100), LIMITED (<100)

### Quick Smoke Test (10 seconds)

```bash
# Read-only throughput
python load-tests/read_only.py -w 5 -d 10

# Mixed workload
python load-tests/read_write.py -w 5 -d 10

# Write-heavy workload
python load-tests/write_heavy.py -w 3 -d 10
```

### Standard Benchmark (30 seconds)

```bash
make benchmark
```

### Full Benchmark Suite (5 minutes per test)

```bash
# Read-only throughput
python load-tests/read_only.py --workers 50 --duration 300 --output results/read_only.json

# Mixed workload
python load-tests/read_write.py --workers 30 --duration 300 --output results/read_write.json

# Write-heavy workload
python load-tests/write_heavy.py --workers 20 --duration 300 --output results/write_heavy.json
```

### Concurrent Connections Test

```bash
# Quick test (100 connections)
python load-tests/concurrent_connections.py -c 100 -b 10

# Full test (1000 connections)
python load-tests/concurrent_connections.py -c 1000 -b 50 --output results/connections.json
```

### Vector Operations

```bash
# 8-dimensional euclidean distance
python load-tests/vector_distance.py --dimensions 8 --iterations 100

# Test different distance types
python load-tests/vector_distance.py -d 8 -t cosine -i 100
python load-tests/vector_distance.py -d 8 -t manhattan -i 100
```

## Data Generators

Generate test data for benchmarks:

### Social Graph

```bash
# Small graph (100 users)
python data-generators/social_graph.py --users 100

# Medium graph (1000 users)
python data-generators/social_graph.py --users 1000 --friends 20 --posts 10
```

### Knowledge Graph

```bash
# Small knowledge graph
python data-generators/knowledge_graph.py --entities 100

# Larger with more relationships
python data-generators/knowledge_graph.py --entities 1000 --relationships 5
```

### Scale Test Data

```bash
# 10K nodes
python data-generators/scale_test.py --nodes 10000 --rels-per-node 5

# 100K nodes (for stress testing)
python data-generators/scale_test.py --nodes 100000 --batch-size 1000
```

## Configuration

Benchmark parameters can be configured via YAML files in `config/`:

### Throughput Configuration (`config/throughput.yaml`)

```yaml
profiles:
  smoke:
    duration_seconds: 10
    workers: 5
  standard:
    duration_seconds: 30
    workers: 10
  full:
    duration_seconds: 60
    workers: 50
```

### Latency Configuration (`config/latency.yaml`)

```yaml
profiles:
  smoke:
    iterations: 100
    warmup_iterations: 10
  standard:
    iterations: 1000
    warmup_iterations: 100
```

## Interpreting Results

Results are saved as JSON files with:

- `throughput_qps` / `throughput_ops` / `throughput_wps`: Operations per second achieved
- `latency_p50_ms`: 50th percentile latency
- `latency_p95_ms`: 95th percentile latency
- `latency_p99_ms`: 99th percentile latency
- `errors` / `failed_*`: Number of failed operations
- `status`: VERIFIED, PARTIAL, or FAILED
- `achieved_percentage`: Percentage of claimed maximum achieved

### Verification Status

| Status | Meaning |
|--------|---------|
| VERIFIED | Achieved >= claimed maximum |
| PARTIAL | Achieved >= minimum acceptable (10% of claimed for throughput) |
| FAILED | Below minimum acceptable threshold |

### Example Output

```json
{
  "benchmark_name": "read_only_throughput",
  "timestamp": "2025-01-26T12:00:00Z",
  "duration_seconds": 30.02,
  "total_queries": 1250,
  "successful_queries": 1248,
  "failed_queries": 2,
  "throughput_qps": 41.6,
  "latency_p50_ms": 23.45,
  "latency_p95_ms": 45.67,
  "latency_p99_ms": 78.90,
  "claimed_max_qps": 100000,
  "achieved_percentage": 0.04,
  "status": "PARTIAL"
}
```

**Note**: When running via shell subprocess (as these benchmarks do), throughput will be significantly lower than claimed server-side maximums due to subprocess overhead. Server-side benchmarks would show true throughput.

## Hardware Recommendations

For accurate benchmark results:

- **CPU**: 8+ cores
- **RAM**: 16+ GB
- **Storage**: NVMe SSD
- **Network**: Low latency connection to Geode server

## CI/CD Integration

The benchmarks integrate with GitLab CI/CD:

```bash
# Run CI benchmark profile
make benchmark-ci

# Generate benchmark report
make benchmark-report
```

## Notes

- "Up to" claims represent best-case scenarios with optimal hardware
- CI/CD benchmarks use shorter durations and may show lower numbers
- **Shell subprocess benchmarks** (`read_only.py`, etc.) have significant overhead (~50ms/query)
- **Native client benchmarks** (`multi_client_benchmark.py`) use persistent QUIC connections for true throughput
- For accurate throughput measurement, always use native client benchmarks
- Compare results across consistent hardware configurations

## CANARY Markers

Each benchmark file includes CANARY markers for traceability:

```python
# CANARY: REQ=REQ-PERF-READ-001; FEATURE="ReadThroughput"; ASPECT=Performance; STATUS=TESTED
```

This links benchmarks to:
- Documentation claims (geodedb.com)
- Server implementation (geode/)
- Verification tests (verification/)
