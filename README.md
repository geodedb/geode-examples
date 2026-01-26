# Geode Examples

Reproducible examples and verification tests for [Geode](https://geodedb.com), the enterprise-ready graph database with 100% ISO/IEC 39075:2024 GQL compliance.

## Purpose

This repository serves two purposes:

1. **User Examples**: Working examples demonstrating Geode features for learning and reference
2. **Claim Verification**: Black-box testing that validates ALL claims made in the [Geode documentation](https://geodedb.com)

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Make
- (Optional) Python 3.12+ for running benchmarks
- (Optional) Go 1.24+, Rust 1.70+, Zig 0.15.1+ for client examples

### Setup

```bash
# Clone the repository
git clone https://gitlab.com/devnw/codepros/geode/geode-examples.git
cd geode-examples

# Set up the environment (builds and starts Geode)
make setup

# Verify Geode is running
make status

# Connect to Geode shell
make shell
```

### Run Tests

```bash
# Run all tests
make test

# Run specific test categories
make test-gql        # GQL compliance tests
make test-clients    # Client library tests
make test-features   # Feature verification
make test-security   # Security tests
```

### Run Benchmarks

```bash
# Run all benchmarks
make benchmark

# Run specific benchmarks
make benchmark-throughput  # Throughput tests
make benchmark-latency     # Latency tests
```

## Repository Structure

```
geode-examples/
├── gql/                    # GQL query examples
│   ├── basic/              # Basic CRUD operations
│   ├── advanced/           # Advanced patterns
│   ├── transactions/       # Transaction examples
│   ├── indexing/           # Index creation and usage
│   └── use-cases/          # Real-world use case examples
│
├── benchmarks/             # Performance benchmarks
│   ├── load-tests/         # Throughput and latency tests
│   └── data-generators/    # Test data generators
│
├── verification/           # Claim verification tests
│   └── claims/             # Tests organized by claim category
│
├── clients/                # Client library examples
│   ├── go/                 # Go examples
│   ├── python/             # Python examples
│   ├── rust/               # Rust examples
│   ├── zig/                # Zig examples
│   └── nodejs/             # Node.js examples
│
├── tutorials/              # Step-by-step tutorials
│   ├── 01_getting_started/
│   ├── 02_pattern_matching/
│   ├── 03_transactions/
│   ├── 04_vector_search/
│   ├── 05_graph_algorithms/
│   └── 06_production_deployment/
│
├── docker/                 # Docker configurations
├── helm/                   # Kubernetes Helm charts
├── configs/                # Configuration examples
└── scripts/                # Automation scripts
```

## Configuration Examples

### Server Configurations

| Configuration | Use Case |
|---------------|----------|
| `configs/server/minimal.yaml` | Quick testing, minimal resources |
| `configs/server/development.yaml` | Local development |
| `configs/server/production.yaml` | Production deployment |
| `configs/server/security-hardened.yaml` | Compliance environments |
| `configs/server/high-performance.yaml` | Maximum throughput |

### Using Custom Configuration

```bash
# Start with specific configuration
docker compose run -v ./configs/server/production.yaml:/etc/geode/geode.yaml geode
```

## Kubernetes Deployment

### Using Helm

```bash
# Install with default values
helm install geode ./helm/geode

# Install with production values
helm install geode ./helm/geode -f ./helm/geode/values.production.yaml

# Upgrade existing installation
helm upgrade geode ./helm/geode
```

### Available Helm Charts

- `helm/geode/` - Single-node Geode deployment
- `helm/geode-cluster/` - Multi-shard cluster deployment
- `helm/monitoring/` - Prometheus/Grafana stack

## Claim Verification

This repository verifies ALL claims made in the Geode documentation:

### Claim Categories

| Category | Claims | Description |
|----------|--------|-------------|
| Compliance | 5 | ISO GQL compliance, test coverage |
| Performance | 8 | Throughput, latency, I/O improvements |
| Security | 8 | Encryption, authentication, audit |
| Scalability | 4 | Connections, shards, data volume |
| Features | 8 | Data types, indexes, algorithms |
| Clients | 5 | Client library capabilities |

### Running Verification

```bash
# Run full verification
make verify

# Generate verification report
make report

# View report
open public/index.html
```

### CANARY Cross-Reference

Claims are cross-referenced with CANARY markers in the Geode codebase:

```bash
# Generate cross-reference report
make verify-canary

# View report
cat docs/CANARY_CROSSREF.md
```

## Examples

### Basic GQL Examples

```gql
-- Create nodes
CREATE (alice:Person {name: 'Alice', age: 30}),
       (bob:Person {name: 'Bob', age: 25}),
       (alice)-[:KNOWS {since: 2020}]->(bob);

-- Pattern matching
MATCH (a:Person)-[:KNOWS]->(b:Person)
WHERE a.age > b.age
RETURN a.name, b.name;

-- Aggregation
MATCH (p:Person)
RETURN avg(p.age) AS average_age, count(p) AS total;
```

### Client Examples

**Go:**
```go
import _ "go.codepros.org/geode/driver"

db, _ := sql.Open("geode", "geode://localhost:3141")
rows, _ := db.Query("MATCH (p:Person) RETURN p.name")
```

**Python:**
```python
from geode_client import GeodeClient

async with GeodeClient("localhost:3141") as client:
    result = await client.execute("MATCH (p:Person) RETURN p.name")
```

**Rust:**
```rust
let client = GeodeClient::connect("localhost:3141").await?;
let result = client.execute("MATCH (p:Person) RETURN p.name").await?;
```

## CI/CD

This repository includes a complete GitLab CI/CD pipeline that:

1. Builds Docker images
2. Runs all GQL compliance tests
3. Tests all client libraries
4. Executes benchmarks
5. Verifies documented claims
6. Generates verification reports

### Running CI Locally

```bash
# Run full CI pipeline
make ci

# Run quick checks only
make ci-quick
```

## Contributing

Contributions are welcome!

### Adding New Examples

1. Add GQL examples to the appropriate `gql/` subdirectory
2. Include CANARY marker comments linking to requirements
3. Add verification tests if the example demonstrates a claim
4. Update documentation

### Adding New Verification Tests

1. Identify the claim to verify from geodedb.com
2. Create test in `verification/claims/` under appropriate category
3. Link to CANARY markers using `# CANARY: REQ=...` comments
4. Run `make verify` to validate

## Documentation

- [Full Plan](docs/PLAN.md) - Complete implementation plan
- [Claims Registry](docs/CLAIMS_REGISTRY.md) - All tracked claims
- [CANARY Cross-Reference](docs/CANARY_CROSSREF.md) - Code traceability
- [Verification Report](docs/VERIFICATION_REPORT.md) - Current verification status

## Tutorials

Step-by-step guides for learning Geode:

1. [Getting Started](tutorials/01_getting_started/) - Basic nodes, relationships, queries
2. [Pattern Matching](tutorials/02_pattern_matching/) - Advanced patterns and paths
3. [Transactions](tutorials/03_transactions/) - ACID, savepoints, isolation
4. [Vector Search](tutorials/04_vector_search/) - HNSW indexes, semantic search
5. [Graph Algorithms](tutorials/05_graph_algorithms/) - 20+ built-in algorithms
6. [Production Deployment](tutorials/06_production_deployment/) - Docker, K8s, HA

## Links

- [Geode Documentation](https://geodedb.com)
- [Geode Repository](https://gitlab.com/devnw/codepros/geode/geode)
- [Issue Tracker](https://gitlab.com/devnw/codepros/geode/geode-examples/-/issues)

## License

Apache License 2.0

Copyright 2024-2025 CodePros
