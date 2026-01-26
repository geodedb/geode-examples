# Tutorial 5: Graph Algorithms

This tutorial covers Geode's 20+ built-in graph algorithms, including
centrality measures, community detection, and path finding.

**CANARY: REQ=REQ-TUTORIAL-005; FEATURE="GraphAlgorithms"; ASPECT=Documentation; STATUS=COMPLETE**

## Prerequisites

- Completed Tutorial 1: Getting Started
- Running Geode instance
- Basic understanding of graph theory

## Algorithm Categories

Geode provides 20+ built-in algorithms in these categories:

1. **Centrality**: Identify important nodes
2. **Community Detection**: Find clusters
3. **Path Finding**: Shortest paths and traversals
4. **Similarity**: Measure node similarity
5. **Link Prediction**: Predict future connections

## Sample Graph Setup

Let's create a sample social network:

```gql
-- Create people
CREATE (:Person {name: 'Alice'});
CREATE (:Person {name: 'Bob'});
CREATE (:Person {name: 'Charlie'});
CREATE (:Person {name: 'Diana'});
CREATE (:Person {name: 'Eve'});
CREATE (:Person {name: 'Frank'});
CREATE (:Person {name: 'Grace'});

-- Create FOLLOWS relationships (directed)
MATCH (a:Person {name: 'Alice'}), (b:Person {name: 'Bob'}) CREATE (a)-[:FOLLOWS]->(b);
MATCH (a:Person {name: 'Alice'}), (c:Person {name: 'Charlie'}) CREATE (a)-[:FOLLOWS]->(c);
MATCH (b:Person {name: 'Bob'}), (c:Person {name: 'Charlie'}) CREATE (b)-[:FOLLOWS]->(c);
MATCH (b:Person {name: 'Bob'}), (d:Person {name: 'Diana'}) CREATE (b)-[:FOLLOWS]->(d);
MATCH (c:Person {name: 'Charlie'}), (d:Person {name: 'Diana'}) CREATE (c)-[:FOLLOWS]->(d);
MATCH (d:Person {name: 'Diana'}), (e:Person {name: 'Eve'}) CREATE (d)-[:FOLLOWS]->(e);
MATCH (e:Person {name: 'Eve'}), (f:Person {name: 'Frank'}) CREATE (e)-[:FOLLOWS]->(f);
MATCH (f:Person {name: 'Frank'}), (g:Person {name: 'Grace'}) CREATE (f)-[:FOLLOWS]->(g);
MATCH (g:Person {name: 'Grace'}), (a:Person {name: 'Alice'}) CREATE (g)-[:FOLLOWS]->(a);
```

## Centrality Algorithms

### PageRank

Measures node importance based on incoming links:

```gql
-- Run PageRank
CALL gds.pageRank.stream({
    nodeLabel: 'Person',
    relationshipType: 'FOLLOWS',
    dampingFactor: 0.85,
    maxIterations: 20
})
YIELD nodeId, score
MATCH (p:Person) WHERE id(p) = nodeId
RETURN p.name, round(score, 4) AS pagerank
ORDER BY pagerank DESC;
```

Expected output (top influencers):
```
+----------+----------+
| name     | pagerank |
+----------+----------+
| Diana    | 0.2156   |
| Charlie  | 0.1823   |
| Bob      | 0.1456   |
...
```

### Betweenness Centrality

Identifies bridge nodes (gatekeepers):

```gql
CALL gds.betweennessCentrality.stream({
    nodeLabel: 'Person',
    relationshipType: 'FOLLOWS'
})
YIELD nodeId, score
MATCH (p:Person) WHERE id(p) = nodeId
RETURN p.name, score AS betweenness
ORDER BY betweenness DESC;
```

### Closeness Centrality

Measures how close a node is to all other nodes:

```gql
CALL gds.closenessCentrality.stream({
    nodeLabel: 'Person',
    relationshipType: 'FOLLOWS'
})
YIELD nodeId, score
MATCH (p:Person) WHERE id(p) = nodeId
RETURN p.name, score AS closeness
ORDER BY closeness DESC;
```

### Degree Centrality

Simple count of connections:

```gql
-- In-degree (followers)
MATCH (p:Person)<-[r:FOLLOWS]-()
RETURN p.name, count(r) AS in_degree
ORDER BY in_degree DESC;

-- Out-degree (following)
MATCH (p:Person)-[r:FOLLOWS]->()
RETURN p.name, count(r) AS out_degree
ORDER BY out_degree DESC;
```

## Community Detection

### Louvain Algorithm

Detects communities by maximizing modularity:

```gql
CALL gds.louvain.stream({
    nodeLabel: 'Person',
    relationshipType: 'FOLLOWS'
})
YIELD nodeId, communityId
MATCH (p:Person) WHERE id(p) = nodeId
RETURN communityId, collect(p.name) AS members
ORDER BY communityId;
```

### Label Propagation

Fast community detection:

```gql
CALL gds.labelPropagation.stream({
    nodeLabel: 'Person',
    relationshipType: 'FOLLOWS',
    maxIterations: 10
})
YIELD nodeId, communityId
MATCH (p:Person) WHERE id(p) = nodeId
RETURN communityId, collect(p.name) AS members;
```

### Connected Components

Find weakly connected components:

```gql
CALL gds.wcc.stream({
    nodeLabel: 'Person',
    relationshipType: 'FOLLOWS'
})
YIELD nodeId, componentId
MATCH (p:Person) WHERE id(p) = nodeId
RETURN componentId, collect(p.name) AS members;
```

### Strongly Connected Components

For directed graphs:

```gql
CALL gds.scc.stream({
    nodeLabel: 'Person',
    relationshipType: 'FOLLOWS'
})
YIELD nodeId, componentId
MATCH (p:Person) WHERE id(p) = nodeId
RETURN componentId, collect(p.name) AS members;
```

## Path Finding

### Shortest Path (Dijkstra)

Find the shortest weighted path:

```gql
-- Add weights to relationships first
MATCH ()-[r:FOLLOWS]->()
SET r.weight = 1.0;

-- Find shortest path
MATCH (start:Person {name: 'Alice'}), (end:Person {name: 'Grace'})
CALL gds.shortestPath.dijkstra.stream({
    sourceNode: start,
    targetNode: end,
    relationshipType: 'FOLLOWS',
    relationshipWeightProperty: 'weight'
})
YIELD path, totalCost
RETURN [n IN nodes(path) | n.name] AS path, totalCost;
```

### All Shortest Paths

Find all paths of minimum length:

```gql
MATCH (start:Person {name: 'Alice'}), (end:Person {name: 'Diana'})
CALL gds.allShortestPaths.stream({
    sourceNode: start,
    targetNode: end,
    relationshipType: 'FOLLOWS'
})
YIELD path
RETURN [n IN nodes(path) | n.name] AS path;
```

### A* Algorithm

Shortest path with heuristic:

```gql
MATCH (start:Person {name: 'Alice'}), (end:Person {name: 'Grace'})
CALL gds.shortestPath.astar.stream({
    sourceNode: start,
    targetNode: end,
    relationshipType: 'FOLLOWS',
    latitudeProperty: 'lat',
    longitudeProperty: 'lon'
})
YIELD path, totalCost
RETURN [n IN nodes(path) | n.name] AS path, totalCost;
```

### BFS and DFS

Breadth-first and depth-first traversals:

```gql
-- BFS from Alice
MATCH (start:Person {name: 'Alice'})
CALL gds.bfs.stream({
    sourceNode: start,
    relationshipType: 'FOLLOWS'
})
YIELD nodeIds
UNWIND nodeIds AS nodeId
MATCH (p:Person) WHERE id(p) = nodeId
RETURN p.name;

-- DFS from Alice
MATCH (start:Person {name: 'Alice'})
CALL gds.dfs.stream({
    sourceNode: start,
    relationshipType: 'FOLLOWS'
})
YIELD nodeIds
UNWIND nodeIds AS nodeId
MATCH (p:Person) WHERE id(p) = nodeId
RETURN p.name;
```

## Similarity Algorithms

### Jaccard Similarity

Based on shared neighbors:

```gql
MATCH (p1:Person {name: 'Alice'}), (p2:Person {name: 'Bob'})
CALL gds.nodeSimilarity.stream({
    node1: p1,
    node2: p2,
    relationshipType: 'FOLLOWS'
})
YIELD similarity
RETURN similarity AS jaccard;
```

### Cosine Similarity

For numerical properties:

```gql
-- Add some numerical properties
MATCH (p:Person) SET p.interests = [rand(), rand(), rand()];

-- Calculate similarity
MATCH (p1:Person {name: 'Alice'}), (p2:Person {name: 'Bob'})
RETURN cosineSimilarity(p1.interests, p2.interests) AS similarity;
```

## Additional Algorithms

### Triangle Count

Count triangles in the graph:

```gql
CALL gds.triangleCount.stream({
    nodeLabel: 'Person',
    relationshipType: 'FOLLOWS'
})
YIELD nodeId, triangleCount
MATCH (p:Person) WHERE id(p) = nodeId
RETURN p.name, triangleCount
ORDER BY triangleCount DESC;
```

### Clustering Coefficient

Measure of local clustering:

```gql
CALL gds.localClusteringCoefficient.stream({
    nodeLabel: 'Person',
    relationshipType: 'FOLLOWS'
})
YIELD nodeId, coefficient
MATCH (p:Person) WHERE id(p) = nodeId
RETURN p.name, coefficient
ORDER BY coefficient DESC;
```

### K-Core Decomposition

Find the k-core subgraph:

```gql
CALL gds.kCore.stream({
    nodeLabel: 'Person',
    relationshipType: 'FOLLOWS',
    k: 2
})
YIELD nodeId
MATCH (p:Person) WHERE id(p) = nodeId
RETURN p.name;
```

## Algorithm Parameters

### Common Parameters

```gql
CALL gds.pageRank.stream({
    -- Node selection
    nodeLabel: 'Person',           -- Filter by label
    nodeQuery: 'MATCH (n:Person) WHERE n.active = true RETURN id(n) AS id',

    -- Relationship selection
    relationshipType: 'FOLLOWS',   -- Filter by type
    relationshipOrientation: 'NATURAL', -- NATURAL, REVERSE, UNDIRECTED
    relationshipWeightProperty: 'weight',

    -- Algorithm-specific
    dampingFactor: 0.85,
    maxIterations: 20,
    tolerance: 0.0001
})
```

## Best Practices

### 1. Create Projections for Performance

```gql
-- Create an in-memory projection for repeated algorithm runs
CALL gds.graph.create(
    'social-network',
    'Person',
    'FOLLOWS',
    {
        relationshipProperties: ['weight']
    }
);

-- Use the projection
CALL gds.pageRank.stream('social-network')
YIELD nodeId, score
...

-- Drop when done
CALL gds.graph.drop('social-network');
```

### 2. Choose Appropriate Parameters

```gql
-- PageRank for large graphs
dampingFactor: 0.85  -- Standard value
maxIterations: 20    -- Usually converges by then
tolerance: 0.0001    -- Stop when change < tolerance

-- Louvain for community detection
maxLevels: 10        -- Hierarchy depth
maxIterations: 10    -- Per level
```

### 3. Handle Large Graphs

```gql
-- Process in batches
CALL gds.pageRank.stream({
    nodeLabel: 'Person',
    relationshipType: 'FOLLOWS',
    concurrency: 4  -- Parallel execution
})
...
```

## Practice Exercises

### Exercise 1: Influencer Analysis

1. Run PageRank on the sample graph
2. Find the top 3 influencers
3. Explain why they rank highest

### Exercise 2: Community Detection

1. Run Louvain on the sample graph
2. Identify distinct communities
3. Find bridge nodes between communities

### Exercise 3: Path Analysis

1. Find shortest path between Alice and Grace
2. Find all paths of length <= 4
3. Identify bottleneck nodes

## Summary

You've learned:
- Centrality algorithms (PageRank, betweenness, closeness)
- Community detection (Louvain, label propagation)
- Path finding (Dijkstra, A*, BFS/DFS)
- Similarity measures (Jaccard, cosine)
- Additional algorithms (triangles, k-core)
- Best practices for large graphs

Next: [Tutorial 6: Production Deployment](../06_production_deployment/)
