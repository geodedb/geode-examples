# Geode Claims Registry

This document tracks all claims made in geodedb.com documentation and their verification status.

**CANARY: REQ=REQ-DOCS-CLAIMS-001; FEATURE="ClaimsRegistry"; ASPECT=Documentation; STATUS=COMPLETE**

## Overview

This registry catalogs every testable claim from the Geode documentation, linking each to:
- Source documentation
- CANARY requirement ID
- Verification test
- Current status

## Claim Status Legend

| Status | Description |
|--------|-------------|
| VERIFIED | Claim tested and confirmed |
| PARTIAL | Claim partially verified (environment limitations) |
| PENDING | Test exists but not yet run |
| UNVERIFIED | No test exists yet |

---

## Category 1: Standards Compliance

| Claim ID | Claim | Source | CANARY REQ | Test File | Status |
|----------|-------|--------|------------|-----------|--------|
| CLAIM-ISO-001 | 100% ISO/IEC 39075:2024 GQL compliance | Features Overview | REQ-ISO-001 | `verification/claims/compliance/iso_gql_70_tests.py` | VERIFIED |
| CLAIM-ISO-002 | 70/70 official tests passing | Overview | REQ-ISO-002 | `verification/claims/compliance/iso_gql_70_tests.py` | VERIFIED |
| CLAIM-GQL-001 | Full pattern matching syntax | GQL Guide | REQ-GQL-PATTERN-001 | `gql/basic/003_pattern_matching.gql` | VERIFIED |
| CLAIM-GQL-002 | Full aggregation support | Features | REQ-GQL-AGG-001 | `gql/basic/004_aggregations.gql` | VERIFIED |
| CLAIM-GQL-003 | Set operations (UNION, INTERSECT, EXCEPT) | Features | REQ-GQL-SET-001 | `gql/advanced/set_operations.gql` | VERIFIED |
| CLAIM-GQL-004 | Subqueries and CTEs | Features | REQ-GQL-SUB-001 | `gql/advanced/subqueries.gql` | VERIFIED |
| CLAIM-GQL-005 | Map literals support | Features | REQ-GQL-MAP-001 | `gql/advanced/map_literals.gql` | VERIFIED |

---

## Category 2: Performance Claims

| Claim ID | Claim | Source | CANARY REQ | Test File | Status |
|----------|-------|--------|------------|-----------|--------|
| CLAIM-PERF-001 | Read-only: up to 100,000 txn/sec | Overview, Performance | REQ-PERF-READ-001 | `benchmarks/load-tests/read_only.py` | PARTIAL |
| CLAIM-PERF-002 | Read-write: 10,000-50,000 txn/sec | Overview, Performance | REQ-PERF-RW-001 | `benchmarks/load-tests/read_write.py` | PARTIAL |
| CLAIM-PERF-003 | Write-heavy: 5,000-20,000 txn/sec | Overview, Performance | REQ-PERF-WRITE-001 | `benchmarks/load-tests/write_heavy.py` | PARTIAL |
| CLAIM-PERF-004 | Vector distance: <50ns (8D L2) | Features, Performance | REQ-PERF-VECTOR-001 | `benchmarks/load-tests/vector_distance.py` | PARTIAL |
| CLAIM-PERF-005 | Memory-mapped I/O: 13.18x improvement | Overview, Features | REQ-PERF-MMAP-001 | `verification/claims/performance/mmap_improvement.py` | PENDING |
| CLAIM-PERF-006 | HNSW recall: ~90% | Overview | REQ-PERF-HNSW-001 | `verification/claims/features/vector_search.py` | VERIFIED |
| CLAIM-PERF-007 | BM25: 10-50us single-term | Performance | REQ-PERF-BM25-001 | `verification/claims/performance/latency_claims.py` | PENDING |

---

## Category 3: Scalability Claims

| Claim ID | Claim | Source | CANARY REQ | Test File | Status |
|----------|-------|--------|------------|-----------|--------|
| CLAIM-SCALE-001 | 10,000+ concurrent connections | Performance | REQ-SCALE-CONN-001 | `benchmarks/load-tests/concurrent_connections.py` | PARTIAL |
| CLAIM-SCALE-002 | Up to 32 shards tested | Features, Distributed | REQ-SCALE-SHARD-001 | `verification/claims/scalability/shard_distribution.py` | PENDING |
| CLAIM-SCALE-003 | 100M+ nodes, 1B+ relationships | Overview | REQ-SCALE-DATA-001 | `benchmarks/data-generators/scale_test.py` | PENDING |
| CLAIM-SCALE-004 | Vector dimensions: up to 65,535 | Features | REQ-SCALE-VECTOR-001 | `verification/claims/features/vector_search.py` | VERIFIED |

---

## Category 4: Security Claims

| Claim ID | Claim | Source | CANARY REQ | Test File | Status |
|----------|-------|--------|------------|-----------|--------|
| CLAIM-SEC-001 | TDE with <1% overhead | Overview, Features | REQ-SEC-TDE-001 | `verification/claims/security/tde_encryption.py` | VERIFIED |
| CLAIM-SEC-002 | AES-256-GCM encryption | Security | REQ-SEC-AES-001 | `verification/claims/security/tde_encryption.py` | VERIFIED |
| CLAIM-SEC-003 | TLS 1.3 only | Features | REQ-SEC-TLS-001 | `verification/claims/security/tls_protocol.py` | VERIFIED |
| CLAIM-SEC-004 | QUIC transport (no TCP fallback) | Features | REQ-SEC-QUIC-001 | `verification/claims/security/quic_transport.py` | VERIFIED |
| CLAIM-SEC-005 | RLS with policy evaluation | Security | REQ-SEC-RLS-001 | `verification/claims/security/rls_policies.py` | VERIFIED |
| CLAIM-SEC-006 | MFA with TOTP | Features | REQ-SEC-MFA-001 | `verification/claims/security/mfa_totp.py` | VERIFIED |
| CLAIM-SEC-007 | Comprehensive audit logging | Security | REQ-SEC-AUDIT-001 | `verification/claims/security/audit_logging.py` | VERIFIED |
| CLAIM-SEC-008 | Argon2id password hashing | Security | REQ-SEC-HASH-001 | `verification/claims/security/password_hashing.py` | VERIFIED |

---

## Category 5: Feature Claims

| Claim ID | Claim | Source | CANARY REQ | Test File | Status |
|----------|-------|--------|------------|-----------|--------|
| CLAIM-FEAT-001 | 50+ specialized data types | Features | REQ-TYPES-001 | `verification/claims/features/data_types_50plus.py` | PENDING |
| CLAIM-FEAT-002 | 6 index types | Features | REQ-INDEX-001 | `gql/indexing/all_index_types.gql` | VERIFIED |
| CLAIM-FEAT-003 | 6 isolation levels | Features | REQ-TXN-ISO-001 | `verification/claims/features/transaction_features.py` | VERIFIED |
| CLAIM-FEAT-004 | 20+ built-in algorithms | Features | REQ-ALGO-001 | `verification/claims/features/graph_algorithms.py` | VERIFIED |
| CLAIM-FEAT-005 | Savepoint support | Transactions | REQ-TXN-SAVE-001 | `verification/claims/features/transaction_features.py` | VERIFIED |
| CLAIM-FEAT-006 | EXPLAIN and PROFILE | GQL Guide | REQ-GQL-EXPLAIN-001 | `gql/advanced/explain_profile.gql` | VERIFIED |

---

## Category 6: Client Library Claims

| Claim ID | Claim | Source | CANARY REQ | Test File | Status |
|----------|-------|--------|------------|-----------|--------|
| CLAIM-CLIENT-001 | Go: database/sql driver | Client Docs | REQ-CLIENT-GO-001 | `clients/go/examples/basic_connection/main.go` | VERIFIED |
| CLAIM-CLIENT-002 | Go: connection pooling | Client Docs | REQ-CLIENT-GO-POOL-001 | `clients/go/examples/connection_pooling/main.go` | VERIFIED |
| CLAIM-CLIENT-003 | Python: async client | Client Docs | REQ-CLIENT-PYTHON-001 | `clients/python/examples/async_queries/main.py` | VERIFIED |
| CLAIM-CLIENT-004 | Python: 1000+ queries/sec | Client Docs | REQ-CLIENT-PYTHON-PERF-001 | `clients/python/examples/async_queries/main.py` | PARTIAL |
| CLAIM-CLIENT-005 | Rust: tokio integration | Client Docs | REQ-CLIENT-RUST-001 | `clients/rust/examples/basic_usage/main.rs` | VERIFIED |
| CLAIM-CLIENT-006 | Rust: 10,000+ queries/sec | Client Docs | REQ-CLIENT-RUST-PERF-001 | `clients/rust/examples/high_throughput/main.rs` | PARTIAL |
| CLAIM-CLIENT-007 | Zig: native client | Client Docs | REQ-CLIENT-ZIG-001 | `clients/zig/examples/basic/main.zig` | VERIFIED |
| CLAIM-CLIENT-008 | All clients: transactions | Client Docs | REQ-CLIENT-TXN-001 | Multiple | VERIFIED |
| CLAIM-CLIENT-009 | Node.js: async/await | Client Docs | REQ-CLIENT-NODEJS-001 | `clients/nodejs/examples/basic_connection/index.js` | VERIFIED |

---

## Category 7: Test Coverage Claims

| Claim ID | Claim | Source | CANARY REQ | Test File | Status |
|----------|-------|--------|------------|-----------|--------|
| CLAIM-TEST-001 | 97.4% test coverage (1644/1688) | Overview, Features | REQ-TEST-COV-001 | N/A (internal) | UNVERIFIED |
| CLAIM-TEST-002 | 100% unit test pass (393/393) | Overview | REQ-TEST-UNIT-001 | N/A (internal) | UNVERIFIED |
| CLAIM-TEST-003 | 1,735 CANARY markers | Overview, Features | REQ-CANARY-001 | `scripts/compare_canary.sh` | PENDING |

---

## Summary Statistics

| Category | Total Claims | Verified | Partial | Pending | Unverified |
|----------|-------------|----------|---------|---------|------------|
| Standards Compliance | 7 | 7 | 0 | 0 | 0 |
| Performance | 7 | 1 | 4 | 2 | 0 |
| Scalability | 4 | 1 | 1 | 2 | 0 |
| Security | 8 | 8 | 0 | 0 | 0 |
| Features | 6 | 5 | 0 | 1 | 0 |
| Client Libraries | 9 | 7 | 2 | 0 | 0 |
| Test Coverage | 3 | 0 | 0 | 1 | 2 |
| **Total** | **44** | **29** | **7** | **6** | **2** |

**Verification Rate: 81.8%** (36/44 verified or partially verified)

---

## Notes

### Partial Verifications

Performance and throughput claims are marked as "PARTIAL" because:
1. Actual throughput depends on hardware
2. CI/CD environment has resource limitations
3. "Up to X" claims represent best-case scenarios

These claims are verified to work correctly; absolute numbers may vary by environment.

### Unverified Claims

Test coverage claims (CLAIM-TEST-001, CLAIM-TEST-002) cannot be verified externally as they relate to internal Geode test suite metrics.

### Adding New Claims

When documentation is updated:
1. Extract new claims using `scripts/extract_all_claims.sh`
2. Add entry to this registry
3. Create verification test
4. Link to CANARY marker in geode codebase
5. Run verification and update status

---

**Last Updated**: January 2026
**Registry Version**: 1.0
