# CANARY Cross-Reference

This document provides cross-references between claims in geodedb.com documentation
and CANARY markers in the geode codebase.

**CANARY: REQ=REQ-DOCS-CANARY-001; FEATURE="CANARYCrossRef"; ASPECT=Documentation; STATUS=COMPLETE**

## Overview

CANARY markers are governance tokens embedded in the geode codebase that track
requirement implementation status. This document maps external documentation claims
to internal CANARY markers for traceability.

## CANARY Marker Format

```
CANARY: REQ=<requirement-id>; FEATURE="<feature-name>"; ASPECT=<aspect>; STATUS=<status>
```

| Field | Description | Example |
|-------|-------------|---------|
| REQ | Unique requirement identifier | REQ-GQL-001 |
| FEATURE | Human-readable feature name | "GQLCompliance" |
| ASPECT | Category (GQL, Security, Performance, Client, etc.) | GQL |
| STATUS | IMPLEMENTED, TESTED, VERIFIED | TESTED |

---

## Cross-Reference by Category

### GQL Compliance

| Doc Claim | CANARY REQ | geode File | Status |
|-----------|------------|------------|--------|
| ISO GQL compliance | REQ-ISO-001 | `src/gql/parser.zig` | TESTED |
| Pattern matching | REQ-GQL-PATTERN-001 | `src/gql/pattern.zig` | TESTED |
| Aggregations | REQ-GQL-AGG-001 | `src/gql/aggregation.zig` | TESTED |
| Set operations | REQ-GQL-SET-001 | `src/gql/set_ops.zig` | TESTED |
| Transactions | REQ-GQL-TXN-001 | `src/storage/transaction.zig` | TESTED |
| Savepoints | REQ-GQL-SAVE-001 | `src/storage/savepoint.zig` | TESTED |

### Performance

| Doc Claim | CANARY REQ | geode File | Status |
|-----------|------------|------------|--------|
| 100k read txn/sec | REQ-PERF-READ-001 | `src/server/connection.zig` | TESTED |
| Memory-mapped I/O | REQ-PERF-MMAP-001 | `src/storage/mmap.zig` | TESTED |
| Vector distance | REQ-PERF-VECTOR-001 | `src/index/vector.zig` | TESTED |
| HNSW index | REQ-PERF-HNSW-001 | `src/index/hnsw.zig` | TESTED |
| BM25 ranking | REQ-PERF-BM25-001 | `src/index/fulltext.zig` | TESTED |

### Security

| Doc Claim | CANARY REQ | geode File | Status |
|-----------|------------|------------|--------|
| TDE encryption | REQ-SEC-TDE-001 | `src/security/tde.zig` | TESTED |
| AES-256-GCM | REQ-SEC-AES-001 | `src/security/crypto.zig` | TESTED |
| TLS 1.3 | REQ-SEC-TLS-001 | `src/network/tls.zig` | TESTED |
| QUIC transport | REQ-SEC-QUIC-001 | `src/network/quic.zig` | TESTED |
| RLS policies | REQ-SEC-RLS-001 | `src/security/rls.zig` | TESTED |
| MFA/TOTP | REQ-SEC-MFA-001 | `src/security/mfa.zig` | TESTED |
| Audit logging | REQ-SEC-AUDIT-001 | `src/security/audit.zig` | TESTED |
| Argon2id | REQ-SEC-HASH-001 | `src/security/password.zig` | TESTED |

### Index Types

| Doc Claim | CANARY REQ | geode File | Status |
|-----------|------------|------------|--------|
| B-tree index | REQ-INDEX-BTREE-001 | `src/index/btree.zig` | TESTED |
| Hash index | REQ-INDEX-HASH-001 | `src/index/hash.zig` | TESTED |
| Full-text index | REQ-INDEX-FT-001 | `src/index/fulltext.zig` | TESTED |
| Vector/HNSW | REQ-INDEX-VECTOR-001 | `src/index/hnsw.zig` | TESTED |
| Spatial/R-tree | REQ-INDEX-SPATIAL-001 | `src/index/rtree.zig` | TESTED |
| Patricia Trie | REQ-INDEX-TRIE-001 | `src/index/trie.zig` | TESTED |

### Client Libraries

| Doc Claim | CANARY REQ | geode File | Status |
|-----------|------------|------------|--------|
| Go client | REQ-CLIENT-GO-001 | `geode-client-go/` | TESTED |
| Python client | REQ-CLIENT-PYTHON-001 | `geode-client-python/` | TESTED |
| Rust client | REQ-CLIENT-RUST-001 | `geode-client-rust/` | TESTED |
| Zig client | REQ-CLIENT-ZIG-001 | `geode-client-zig/` | TESTED |

---

## CANARY Statistics

### By Aspect

| Aspect | Count | Percentage |
|--------|-------|------------|
| GQL | 412 | 23.7% |
| Storage | 328 | 18.9% |
| Security | 287 | 16.5% |
| Index | 245 | 14.1% |
| Network | 189 | 10.9% |
| Client | 156 | 9.0% |
| Other | 118 | 6.8% |
| **Total** | **1,735** | **100%** |

### By Status

| Status | Count | Percentage |
|--------|-------|------------|
| TESTED | 1,644 | 94.8% |
| IMPLEMENTED | 72 | 4.1% |
| VERIFIED | 19 | 1.1% |
| **Total** | **1,735** | **100%** |

---

## Verification Scripts

### Extract CANARY Markers from geode

```bash
./scripts/compare_canary.sh ../geode ../geodedb.com
```

This script:
1. Scans geode codebase for CANARY markers
2. Extracts claims from documentation
3. Generates cross-reference report
4. Identifies unlinked claims

### Sample Output

```
CANARY Cross-Reference Report
=============================
Generated: 2026-01-26

Total CANARY markers in geode: 1,735
Total claims in documentation: 44
Linked claims: 42 (95.5%)
Unlinked claims: 2 (4.5%)

Unlinked Claims:
- CLAIM-TEST-001: 97.4% test coverage (internal metric)
- CLAIM-TEST-002: 100% unit test pass (internal metric)
```

---

## Adding New Cross-References

When implementing a new feature:

1. **In geode codebase**, add CANARY marker:
   ```zig
   // CANARY: REQ=REQ-NEW-FEATURE-001; FEATURE="NewFeature"; ASPECT=Category; STATUS=IMPLEMENTED
   ```

2. **In geodedb.com**, document the feature with claim

3. **In geode-examples**, add verification test:
   ```python
   """
   Verifies claim: New feature description
   Source: Features Overview
   CANARY: REQ=REQ-NEW-FEATURE-001; FEATURE="NewFeature"; ASPECT=Category; STATUS=TESTED
   """
   ```

4. **Update this document** with new cross-reference

5. **Run verification** to confirm linkage

---

## Maintenance

### Weekly Tasks

- Run `compare_canary.sh` to detect drift
- Review any new unlinked claims
- Update status of pending verifications

### On Release

- Verify all CANARY markers are TESTED
- Regenerate cross-reference report
- Update documentation claims if needed

---

**Last Updated**: January 2026
**Cross-Reference Version**: 1.0
