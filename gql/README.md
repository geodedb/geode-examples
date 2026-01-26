# GQL Examples

This directory contains comprehensive GQL query examples that demonstrate Geode's capabilities and verify ISO/IEC 39075:2024 compliance.

## Directory Structure

```
gql/
├── basic/                  # Fundamental GQL operations (9 files)
├── advanced/               # Advanced query patterns (7 files)
├── transactions/           # Transaction management (5 files)
├── indexing/               # Index types and usage (6 files)
└── use-cases/              # Real-world application examples
    ├── social_network/     # Social graph patterns
    ├── fraud_detection/    # Financial fraud patterns
    ├── recommendations/    # Recommendation engines
    ├── knowledge_graph/    # Knowledge management
    └── supply_chain/       # Supply chain tracking
```

## Basic Examples

| File | Description | Key Concepts |
|------|-------------|--------------|
| `001_hello_world.gql` | Simple queries to verify connectivity | RETURN, basic expressions |
| `002_create_nodes.gql` | Node creation with labels and properties | CREATE, labels, properties |
| `003_create_relationships.gql` | Relationship creation | CREATE, relationships |
| `004_pattern_matching.gql` | Pattern matching fundamentals | MATCH, patterns |
| `005_variable_length_paths.gql` | Multi-hop traversals | Variable-length paths |
| `006_aggregations.gql` | Aggregation functions | COUNT, SUM, AVG, MIN, MAX |
| `007_filtering.gql` | WHERE clause filtering | WHERE, boolean expressions |
| `008_ordering_and_limiting.gql` | Result ordering and pagination | ORDER BY, LIMIT, SKIP |
| `009_optional_match.gql` | Left-join patterns | OPTIONAL MATCH |

## Advanced Examples

| File | Description | Key Concepts |
|------|-------------|--------------|
| `001_with_clause.gql` | Query pipelines | WITH, subqueries |
| `002_set_operations.gql` | Set operations | UNION, INTERSECT, EXCEPT |
| `003_subqueries.gql` | Subqueries and EXISTS | EXISTS, subqueries |
| `004_map_literals.gql` | Map/object operations | Maps, projections |
| `005_list_operations.gql` | List comprehensions | Lists, UNWIND |
| `006_case_expressions.gql` | Conditional expressions | CASE, WHEN |
| `007_explain_profile.gql` | Query analysis | EXPLAIN, PROFILE |

## Transaction Examples

| File | Description | Key Concepts |
|------|-------------|--------------|
| `001_basic_transactions.gql` | Transaction basics | START TRANSACTION, COMMIT |
| `002_savepoints.gql` | Savepoint management | SAVEPOINT, ROLLBACK TO |
| `002_rollback.gql` | Rollback scenarios | ROLLBACK |
| `003_isolation_levels.gql` | Isolation levels | Serializable, Snapshot |
| `004_transaction_patterns.gql` | Real-world patterns | Atomic operations |

## Indexing Examples

| File | Description | Key Concepts |
|------|-------------|--------------|
| `001_btree_index.gql` | B-tree indexes | Range queries, sorting |
| `002_hash_index.gql` | Hash indexes | Exact matches |
| `003_fulltext_index.gql` | Full-text search | BM25, text search |
| `004_vector_index.gql` | Vector similarity | HNSW, embeddings |
| `005_spatial_index.gql` | Geographic indexes | R-tree, distance |
| `006_all_index_types.gql` | Index type summary | All 6 types |

## Use Case Examples

### Social Network (`use-cases/social_network/`)

Demonstrates graph patterns for social applications:
- Friend-of-friend queries
- Mutual connections
- Degrees of separation
- Network clustering
- Community detection

### Fraud Detection (`use-cases/fraud_detection/`)

Demonstrates fraud detection patterns:
- Circular transaction detection (money laundering rings)
- Structuring/smurfing detection
- Rapid layering analysis
- Velocity analysis
- Risk scoring

### Recommendations (`use-cases/recommendations/`)

Demonstrates recommendation engine patterns:
- Collaborative filtering (user-user)
- Item-item recommendations
- Content-based filtering
- Trending products
- Cross-category exploration

### Knowledge Graph (`use-cases/knowledge_graph/`)

Demonstrates knowledge graph patterns:
- Entity relationships
- Inference chains
- Multi-hop discovery
- Path finding
- Network analysis

### Supply Chain (`use-cases/supply_chain/`)

Demonstrates supply chain patterns:
- Bill of materials (BOM)
- Supplier analysis
- Critical path analysis
- Inventory tracking
- Risk assessment

## Running Examples

### Using Geode Shell

```bash
# Connect to Geode
geode shell

# Run a single file
geode shell < gql/basic/001_hello_world.gql

# Run all basic examples
for f in gql/basic/*.gql; do echo "=== $f ===" && geode shell < "$f"; done
```

### Using Docker Compose

```bash
# Start Geode
docker compose up -d geode

# Run examples
docker compose exec geode geode shell < gql/basic/001_hello_world.gql
```

### Using Make

```bash
# Run all GQL tests
make test-gql

# Run specific category
make test-gql-basic
make test-gql-advanced
```

## CANARY Markers

Each example file includes a CANARY marker linking it to requirements:

```gql
-- CANARY: REQ=REQ-GQL-001; FEATURE="NodeCreation"; ASPECT=BasicOps; STATUS=TESTED
```

This enables traceability between:
- Documentation claims (geodedb.com)
- Example code (this repository)
- Implementation (geode codebase)

## ISO/IEC 39075:2024 Coverage

These examples cover the following ISO GQL sections:

| ISO Section | Coverage | Examples |
|-------------|----------|----------|
| 8. Pattern Matching | Complete | basic/004, advanced/001-003 |
| 9. Graph Operations | Complete | basic/002-003 |
| 10. Aggregations | Complete | basic/006 |
| 11. Set Operations | Complete | advanced/002 |
| 12. Clauses | Complete | basic/007-009 |
| 13. Expressions | Complete | advanced/004-006 |
| 14. Transactions | Complete | transactions/* |

## Contributing

When adding new examples:

1. Follow the naming convention: `NNN_description.gql`
2. Include a CANARY marker at the top
3. Add setup queries if needed (CREATE statements)
4. Include comments explaining the query
5. Test the example before committing

## Related Documentation

- [Geode GQL Guide](https://geodedb.com/docs/gql/guide/)
- [ISO/IEC 39075:2024](https://www.iso.org/standard/76120.html)
- [Verification Tests](../verification/claims/compliance/)
