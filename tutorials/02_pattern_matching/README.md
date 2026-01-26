# Tutorial 2: Pattern Matching

This tutorial covers advanced pattern matching techniques in GQL, including
variable-length paths, quantified patterns, and path functions.

**CANARY: REQ=REQ-TUTORIAL-002; FEATURE="PatternMatching"; ASPECT=Documentation; STATUS=COMPLETE**

## Prerequisites

- Completed Tutorial 1: Getting Started
- Running Geode instance
- Basic understanding of graph traversal

## Basic Patterns

### Node Patterns

```gql
-- Match all nodes
MATCH (n) RETURN count(n);

-- Match nodes with label
MATCH (p:Person) RETURN p.name;

-- Match nodes with multiple labels
MATCH (e:Person:Employee) RETURN e.name;

-- Match nodes with properties
MATCH (p:Person {name: 'Alice', age: 30})
RETURN p;
```

### Relationship Patterns

```gql
-- Match any relationship
MATCH (a)-[r]->(b) RETURN a.name, type(r), b.name;

-- Match specific relationship type
MATCH (a)-[:KNOWS]->(b) RETURN a.name, b.name;

-- Match relationship with properties
MATCH (a)-[r:KNOWS {since: date('2020-01-15')}]->(b)
RETURN a.name, b.name, r.since;

-- Match undirected relationship
MATCH (a)-[:KNOWS]-(b) RETURN a.name, b.name;
```

## Variable-Length Paths

### Fixed Length

```gql
-- Exactly 2 hops
MATCH (a:Person)-[:KNOWS*2]->(b:Person)
RETURN a.name, b.name;
```

### Range Length

```gql
-- Between 1 and 3 hops
MATCH (a:Person)-[:KNOWS*1..3]->(b:Person)
WHERE a.name = 'Alice'
RETURN b.name, length(path) AS distance;

-- At least 2 hops
MATCH (a:Person)-[:KNOWS*2..]->(b:Person)
RETURN a.name, b.name;

-- At most 3 hops
MATCH (a:Person)-[:KNOWS*..3]->(b:Person)
RETURN a.name, b.name;

-- Any number of hops (be careful!)
MATCH (a:Person)-[:KNOWS*]->(b:Person)
RETURN a.name, b.name;
```

### Named Paths

```gql
-- Assign path to variable
MATCH path = (a:Person {name: 'Alice'})-[:KNOWS*1..3]->(b:Person)
RETURN
    path,
    length(path) AS hops,
    [n IN nodes(path) | n.name] AS names,
    [r IN relationships(path) | r.since] AS since_dates;
```

## Pattern Predicates

### EXISTS Pattern

```gql
-- Find people who know someone
MATCH (p:Person)
WHERE EXISTS { (p)-[:KNOWS]->() }
RETURN p.name;

-- Find people who don't know anyone
MATCH (p:Person)
WHERE NOT EXISTS { (p)-[:KNOWS]->() }
RETURN p.name;
```

### COUNT Pattern

```gql
-- Find people with more than 2 friends
MATCH (p:Person)
WHERE COUNT { (p)-[:KNOWS]->() } > 2
RETURN p.name;
```

### COLLECT Pattern

```gql
-- Get all friend names
MATCH (p:Person {name: 'Alice'})
WHERE EXISTS { (p)-[:KNOWS]->(f:Person) }
RETURN p.name, COLLECT { (p)-[:KNOWS]->(f) | f.name } AS friends;
```

## Quantified Path Patterns

### One or More (+)

```gql
-- Match chains of any length (at least 1)
MATCH (a:Person)((n)-[:FOLLOWS]->(m))+
WHERE a.name = 'Alice'
RETURN a.name, count(*) AS chain_length;
```

### Zero or More (*)

```gql
-- Match paths including the start node
MATCH (a:Person)((n)-[:FOLLOWS]->(m))*
RETURN a.name;
```

### Exact Count ({n})

```gql
-- Match exactly 3 hops
MATCH (a:Person)(()-[:FOLLOWS]->()){{3}}(b:Person)
RETURN a.name, b.name;
```

### Range Count ({n,m})

```gql
-- Match between 2 and 4 hops
MATCH (a:Person)(()-[:FOLLOWS]->()){{2,4}}(b:Person)
RETURN a.name, b.name;
```

## Path Functions

### nodes() and relationships()

```gql
MATCH path = (a:Person)-[:KNOWS*2..4]->(b:Person)
RETURN
    nodes(path) AS all_nodes,
    relationships(path) AS all_rels;
```

### length()

```gql
MATCH path = (a:Person)-[:KNOWS*]->(b:Person)
WHERE length(path) <= 5
RETURN a.name, b.name, length(path) AS hops;
```

### Path Operations

```gql
-- Get first and last node
MATCH path = (a:Person)-[:KNOWS*]->(b:Person)
RETURN
    head(nodes(path)).name AS start,
    last(nodes(path)).name AS end;

-- Get intermediate nodes
MATCH path = (a:Person)-[:KNOWS*3]->(b:Person)
WITH nodes(path) AS ns
RETURN ns[1].name AS middle;
```

## Advanced Patterns

### Multiple Patterns

```gql
-- Match multiple patterns in one query
MATCH (a:Person)-[:KNOWS]->(b:Person),
      (b)-[:WORKS_AT]->(c:Company)
RETURN a.name, b.name, c.name;
```

### Optional Match

```gql
-- Like LEFT JOIN - returns nulls if no match
MATCH (p:Person)
OPTIONAL MATCH (p)-[:WORKS_AT]->(c:Company)
RETURN p.name, c.name;  -- c.name is null if no job
```

### Pattern Comprehensions

```gql
-- Inline pattern matching
MATCH (p:Person)
RETURN
    p.name,
    [(p)-[:KNOWS]->(f) | f.name] AS friends,
    [(p)-[:WORKS_AT]->(c) | c.name] AS companies;
```

## Pattern Filtering

### WHERE on Patterns

```gql
-- Filter on node properties in pattern
MATCH (a:Person)-[:KNOWS]->(b:Person)
WHERE a.age > b.age
RETURN a.name AS older, b.name AS younger;

-- Filter on relationship properties
MATCH (a)-[r:KNOWS]->(b)
WHERE r.since > date('2020-01-01')
RETURN a.name, b.name, r.since;
```

### Path Predicates

```gql
-- All nodes in path satisfy condition
MATCH path = (a:Person)-[:KNOWS*]->(b:Person)
WHERE all(n IN nodes(path) WHERE n.age > 20)
RETURN path;

-- Any node in path satisfies condition
MATCH path = (a:Person)-[:KNOWS*]->(b:Person)
WHERE any(n IN nodes(path) WHERE n.city = 'NYC')
RETURN path;

-- No node satisfies condition
MATCH path = (a:Person)-[:KNOWS*]->(b:Person)
WHERE none(n IN nodes(path) WHERE n.blocked = true)
RETURN path;
```

## Shortest Path

```gql
-- Find shortest path between two nodes
MATCH (a:Person {name: 'Alice'}), (b:Person {name: 'Diana'})
MATCH path = shortestPath((a)-[:KNOWS*]-(b))
RETURN path, length(path);

-- All shortest paths
MATCH (a:Person {name: 'Alice'}), (b:Person {name: 'Diana'})
MATCH path = allShortestPaths((a)-[:KNOWS*]-(b))
RETURN path;
```

## Practice Exercises

### Exercise 1: Friend of Friend

Find all "friends of friends" (2 hops) who are not direct friends:

```gql
MATCH (me:Person {name: 'Alice'})-[:KNOWS*2]->(fof:Person)
WHERE NOT (me)-[:KNOWS]->(fof)
  AND me <> fof
RETURN DISTINCT fof.name;
```

### Exercise 2: Common Connections

Find people who have common connections with Alice:

```gql
MATCH (alice:Person {name: 'Alice'})-[:KNOWS]->(mutual)<-[:KNOWS]-(other:Person)
WHERE alice <> other
RETURN other.name, collect(mutual.name) AS common_friends;
```

### Exercise 3: Shortest Connection Chain

Find the shortest path between two people through the KNOWS network.

## GQL Files

See the `examples/` directory:
- `01_basic_patterns.gql`
- `02_variable_length.gql`
- `03_quantified_patterns.gql`
- `04_path_functions.gql`

## Summary

You've learned:
- Basic node and relationship patterns
- Variable-length paths with ranges
- Pattern predicates (EXISTS, COUNT)
- Quantified patterns (+, *, {n,m})
- Path functions (nodes, relationships, length)
- Advanced filtering techniques
- Shortest path queries

Next: [Tutorial 3: Transactions](../03_transactions/)
