# Tutorial 1: Getting Started with Geode

This tutorial walks you through your first steps with Geode, an enterprise-ready
graph database implementing the ISO/IEC 39075:2024 GQL standard.

**CANARY: REQ=REQ-TUTORIAL-001; FEATURE="GettingStarted"; ASPECT=Documentation; STATUS=COMPLETE**

## Prerequisites

- Docker installed
- A terminal/command prompt
- Basic understanding of graph concepts

## Step 1: Start Geode Server

The simplest way to get started is using Docker:

```bash
# Pull and run Geode
docker run -d \
  --name geode \
  -p 3141:3141 \
  registry.gitlab.com/devnw/codepros/geode/geode:latest

# Verify it's running
docker logs geode
```

Or use docker-compose from this repository:

```bash
cd /path/to/geode-examples
docker compose up -d geode
```

## Step 2: Connect with the Shell

Geode includes an interactive shell:

```bash
# Using Docker
docker exec -it geode geode shell

# Or if installed locally
geode shell --connect localhost:3141
```

You should see the Geode shell prompt:

```
Geode Shell v0.18.0
Connected to localhost:3141
geode>
```

## Step 3: Your First Query

Let's start with a simple query:

```gql
-- Return a simple value
RETURN 'Hello, Geode!' AS greeting;
```

Output:
```
+------------------+
| greeting         |
+------------------+
| Hello, Geode!    |
+------------------+
1 row
```

## Step 4: Create Your First Nodes

Nodes are the fundamental entities in a graph database:

```gql
-- Create a person node
CREATE (:Person {name: 'Alice', age: 30});

-- Create another person
CREATE (:Person {name: 'Bob', age: 25});

-- Verify creation
MATCH (p:Person) RETURN p.name, p.age;
```

Output:
```
+--------+-------+
| p.name | p.age |
+--------+-------+
| Alice  | 30    |
| Bob    | 25    |
+--------+-------+
2 rows
```

## Step 5: Create Relationships

Relationships connect nodes together:

```gql
-- Create a KNOWS relationship between Alice and Bob
MATCH (a:Person {name: 'Alice'}), (b:Person {name: 'Bob'})
CREATE (a)-[:KNOWS {since: date('2020-01-15')}]->(b);

-- Query the relationship
MATCH (a:Person)-[r:KNOWS]->(b:Person)
RETURN a.name, r.since, b.name;
```

Output:
```
+--------+------------+--------+
| a.name | r.since    | b.name |
+--------+------------+--------+
| Alice  | 2020-01-15 | Bob    |
+--------+------------+--------+
1 row
```

## Step 6: Pattern Matching

Pattern matching is the heart of GQL:

```gql
-- Find all people Alice knows
MATCH (alice:Person {name: 'Alice'})-[:KNOWS]->(friend)
RETURN friend.name;

-- Find all relationships
MATCH (a)-[r]->(b)
RETURN a.name, type(r), b.name;
```

## Step 7: Aggregations

Geode supports full aggregation capabilities:

```gql
-- Add more people
CREATE (:Person {name: 'Charlie', age: 35});
CREATE (:Person {name: 'Diana', age: 28});

-- Count and average
MATCH (p:Person)
RETURN
  count(p) AS total,
  avg(p.age) AS average_age,
  min(p.age) AS youngest,
  max(p.age) AS oldest;
```

## Step 8: Cleanup

Clean up your test data:

```gql
-- Delete all Person nodes and their relationships
MATCH (p:Person)
DETACH DELETE p;

-- Verify
MATCH (n) RETURN count(n);
```

## What's Next?

- **Tutorial 2**: Deep dive into [Pattern Matching](../02_pattern_matching/)
- **Tutorial 3**: Learn about [Transactions](../03_transactions/)
- **Tutorial 4**: Explore [Vector Search](../04_vector_search/)
- **Tutorial 5**: Master [Graph Algorithms](../05_graph_algorithms/)
- **Tutorial 6**: Prepare for [Production Deployment](../06_production_deployment/)

## GQL Files

The `examples/` directory contains executable GQL files:

```bash
# Run examples
geode shell < examples/01_create_nodes.gql
geode shell < examples/02_create_relationships.gql
geode shell < examples/03_basic_queries.gql
```

## Troubleshooting

### Connection Refused
If you get "connection refused", ensure Geode is running:
```bash
docker ps | grep geode
```

### TLS Errors
Geode requires TLS. For development, use the built-in self-signed cert:
```bash
geode shell --connect localhost:3141 --insecure
```

### Port Already in Use
Change the port mapping:
```bash
docker run -p 13141:3141 registry.gitlab.com/devnw/codepros/geode/geode:latest
geode shell --connect localhost:13141
```

## Summary

You've learned:
- How to start Geode
- How to connect with the shell
- How to create nodes and relationships
- Basic pattern matching
- Aggregation queries

Continue to the next tutorial for advanced pattern matching techniques.
