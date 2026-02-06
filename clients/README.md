# Geode Client Library Examples

This directory contains examples for all officially supported Geode client libraries.

## Client Libraries

| Language | Directory | Status | Key Features |
|----------|-----------|--------|--------------|
| Go | [go/](go/) | Production | database/sql driver, prepared statements |
| Python | [python/](python/) | Production | Async/await, query builders, RLS support |
| Rust | [rust/](rust/) | Production | Tokio async, zero-cost abstractions |
| Zig | [zig/](zig/) | Production | Native Zig, zero-cost abstractions |
| Node.js | [nodejs/](nodejs/) | Production | ES modules, streaming, async/await |

## Common Patterns

All client libraries demonstrate these common patterns:

### Connection Management
- Basic connection with TLS
- Connection pooling
- Automatic reconnection
- Graceful shutdown

### Query Execution
- Simple queries
- Parameterized queries
- Prepared statements
- Streaming results (where supported)

### Transactions
- Begin/commit/rollback
- Savepoints
- Atomic operations
- Error handling with automatic rollback

## Running Examples

### Go
```bash
cd go
go run examples/basic_connection/main.go
go run examples/transactions/main.go
go run examples/prepared_statements/main.go
go run examples/connection_pooling/main.go
```

### Python
```bash
cd python
pip install -r requirements.txt
python examples/async_queries/main.py
python examples/transactions/main.py
python examples/rls_policies/main.py
python examples/query_builders/main.py
```

### Rust
```bash
cd rust
cargo run --example basic_usage
cargo run --example high_throughput
cargo run --example transactions
cargo run --example connection_pool
```

### Zig
```bash
cd zig
zig build run-basic
zig build run-txn
```

### Node.js
```bash
cd nodejs
npm install
npm run basic
npm run async
npm run transactions
npm run streaming
# Or run all:
npm run all
```

## Prerequisites

All examples require a running Geode server:

```bash
# Start Geode server
cd /path/to/geode
./zig-out/bin/geode serve --listen 0.0.0.0:3141
```

## Connection String Format

All clients connect to Geode using the following format:

```
geode://[username:password@]host:port[?options]
```

Default port: **3141**

### TLS Configuration

All connections use TLS 1.3 over QUIC. For development, you may need to configure certificate paths:

```
# Example for Go
geode://localhost:3141?tls=true&cert=/path/to/cert.pem

# Example for Python
await client.connect("localhost", 3141, tls_config={...})

# Example for Rust
let client = GeodeClient::builder()
    .address("localhost:3141")
    .tls_config(TlsConfig::default())
    .build()
    .await?;
```

## CANARY Requirements Verified

Each example includes CANARY markers that trace to specific feature requirements:

| CANARY ID | Feature | Client |
|-----------|---------|--------|
| REQ-CLIENT-GO-001 | Go database/sql driver | Go |
| REQ-CLIENT-GO-TXN-001 | Go transactions | Go |
| REQ-CLIENT-GO-PREP-001 | Go prepared statements | Go |
| REQ-CLIENT-GO-POOL-001 | Go connection pooling | Go |
| REQ-CLIENT-PYTHON-001 | Python async client | Python |
| REQ-CLIENT-PYTHON-TXN-001 | Python transactions | Python |
| REQ-CLIENT-PYTHON-RLS-001 | Python RLS support | Python |
| REQ-CLIENT-PYTHON-QB-001 | Python query builders | Python |
| REQ-CLIENT-RUST-001 | Rust tokio client | Rust |
| REQ-CLIENT-RUST-PERF-001 | Rust high throughput | Rust |
| REQ-CLIENT-RUST-TXN-001 | Rust transactions | Rust |
| REQ-CLIENT-RUST-POOL-001 | Rust connection pool | Rust |
| REQ-CLIENT-ZIG-001 | Zig native client | Zig |
| REQ-CLIENT-ZIG-TXN-001 | Zig transactions | Zig |
| REQ-CLIENT-NODEJS-001 | Node.js client | Node.js |
| REQ-CLIENT-NODEJS-ASYNC-001 | Node.js async operations | Node.js |
| REQ-CLIENT-NODEJS-TXN-001 | Node.js transactions | Node.js |
| REQ-CLIENT-NODEJS-STREAM-001 | Node.js streaming | Node.js |

## Performance Characteristics

Expected throughput by client (single connection):

| Client | Read Queries/sec | Write Queries/sec |
|--------|------------------|-------------------|
| Go | 10,000+ | 5,000+ |
| Python | 1,000+ | 500+ |
| Rust | 10,000+ | 5,000+ |
| Zig | 10,000+ | 5,000+ |
| Node.js | 5,000+ | 2,500+ |

With connection pooling, these numbers scale with pool size.

## License

Apache License 2.0

Copyright 2024-2026 CodePros
