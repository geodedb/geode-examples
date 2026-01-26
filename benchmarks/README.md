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

## Directory Structure

```
benchmarks/
├── config/              # Benchmark configurations
├── load-tests/          # Load testing scripts
├── data-generators/     # Test data generators
└── results/             # Benchmark results (gitignored)
```

## Prerequisites

```bash
pip install -r requirements.txt
```

## Running Benchmarks

### Quick Benchmark (30 seconds)

```bash
make benchmark
```

### Full Benchmark Suite

```bash
# Read-only throughput
python load-tests/read_only.py --duration 300 --output results/read_only.json

# Mixed workload
python load-tests/read_write.py --duration 300 --output results/read_write.json

# Write-heavy workload
python load-tests/write_heavy.py --duration 300 --output results/write_heavy.json
```

### Vector Operations

```bash
python load-tests/vector_distance.py --dimensions 8 --iterations 100000
```

## Configuration

Benchmark parameters can be configured via YAML files in `config/`:

```yaml
# config/throughput.yaml
target_qps: 100000
duration_seconds: 300
concurrent_clients: 100
warmup_seconds: 30
```

## Interpreting Results

Results are saved as JSON files with:

- `throughput_qps`: Queries per second achieved
- `latency_p50_ms`: 50th percentile latency
- `latency_p99_ms`: 99th percentile latency
- `errors`: Number of failed queries
- `claim_verified`: Whether the documented claim was met

### Example Output

```json
{
  "test": "read_only_throughput",
  "claimed_max_qps": 100000,
  "achieved_qps": 85234,
  "claim_percentage": 85.2,
  "claim_verified": true,
  "latency_p50_ms": 1.2,
  "latency_p99_ms": 5.8,
  "duration_seconds": 300,
  "total_queries": 25570200,
  "errors": 0
}
```

## Hardware Recommendations

For accurate benchmark results:

- **CPU**: 8+ cores
- **RAM**: 16+ GB
- **Storage**: NVMe SSD
- **Network**: Low latency connection to Geode server

## Notes

- "Up to" claims represent best-case scenarios with optimal hardware
- CI/CD benchmarks use shorter durations and may show lower numbers
- Compare results across consistent hardware configurations
