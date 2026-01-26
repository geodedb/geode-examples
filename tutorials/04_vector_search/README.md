# Tutorial 4: Vector Search

This tutorial covers Geode's vector search capabilities, including HNSW indexes,
similarity functions, and semantic search patterns.

**CANARY: REQ=REQ-TUTORIAL-004; FEATURE="VectorSearch"; ASPECT=Documentation; STATUS=COMPLETE**

## Prerequisites

- Completed Tutorial 1: Getting Started
- Running Geode instance
- Basic understanding of vectors and embeddings

## Vector Data Types

Geode supports multiple vector types:

```gql
-- 32-bit float vectors (most common for ML embeddings)
CREATE (:Document {
    title: 'Introduction to Graphs',
    embedding: vectorf32([0.1, 0.2, 0.3, 0.4, ...])
});

-- 64-bit float vectors (higher precision)
CREATE (:Scientific {
    measurement: vectorf64([0.123456789, ...])
});

-- Integer vectors
CREATE (:Fingerprint {
    hash: vectori32([1, 0, 1, 1, 0, ...])
});
```

## Creating Vector Indexes

### HNSW Index (Recommended)

HNSW (Hierarchical Navigable Small World) is the recommended index for similarity search:

```gql
-- Create HNSW index on embedding property
CREATE INDEX doc_embedding_hnsw
ON Document(embedding)
USING HNSW
OPTIONS (
    dimensions: 384,
    metric: 'cosine',
    ef_construction: 128,
    m: 16
);
```

Index parameters:
- **dimensions**: Vector dimension (must match your embeddings)
- **metric**: 'cosine', 'l2' (Euclidean), or 'inner_product'
- **ef_construction**: Build-time accuracy (higher = better quality, slower build)
- **m**: Number of connections per node (higher = better recall, more memory)

## Similarity Functions

### Cosine Similarity

Best for normalized embeddings (e.g., sentence-transformers):

```gql
-- Find similar documents using cosine similarity
MATCH (d:Document)
WHERE cosineSimilarity(d.embedding, $query_vector) > 0.8
RETURN d.title, cosineSimilarity(d.embedding, $query_vector) AS score
ORDER BY score DESC
LIMIT 10;
```

### Euclidean Distance (L2)

Best for non-normalized vectors:

```gql
-- Find nearest documents by Euclidean distance
MATCH (d:Document)
WHERE euclideanDistance(d.embedding, $query_vector) < 0.5
RETURN d.title, euclideanDistance(d.embedding, $query_vector) AS distance
ORDER BY distance ASC
LIMIT 10;
```

### Inner Product

Best for maximum inner product search (MIPS):

```gql
-- Find documents with highest inner product
MATCH (d:Document)
RETURN d.title, innerProduct(d.embedding, $query_vector) AS score
ORDER BY score DESC
LIMIT 10;
```

## Semantic Search Example

### Step 1: Create Documents with Embeddings

```gql
-- Sample documents with pre-computed embeddings
-- (In practice, you'd compute these with a model like sentence-transformers)

CREATE (:Document {
    id: 'doc1',
    title: 'Introduction to Graph Databases',
    content: 'Graph databases store data as nodes and relationships...',
    embedding: vectorf32([0.12, 0.34, -0.56, ...])  -- 384 dimensions
});

CREATE (:Document {
    id: 'doc2',
    title: 'SQL vs NoSQL Databases',
    content: 'Comparing relational and non-relational databases...',
    embedding: vectorf32([0.45, -0.23, 0.67, ...])
});

CREATE (:Document {
    id: 'doc3',
    title: 'Machine Learning Fundamentals',
    content: 'An introduction to supervised and unsupervised learning...',
    embedding: vectorf32([-0.34, 0.78, 0.12, ...])
});
```

### Step 2: Create Vector Index

```gql
CREATE INDEX doc_embedding_hnsw
ON Document(embedding)
USING HNSW
OPTIONS (dimensions: 384, metric: 'cosine');
```

### Step 3: Search for Similar Documents

```gql
-- Query: "How do graph databases work?"
-- Query embedding would be computed by the same model

WITH vectorf32([0.15, 0.32, -0.48, ...]) AS query_embedding
MATCH (d:Document)
WHERE cosineSimilarity(d.embedding, query_embedding) > 0.7
RETURN d.title, d.content,
       cosineSimilarity(d.embedding, query_embedding) AS relevance
ORDER BY relevance DESC
LIMIT 5;
```

## Hybrid Search

Combine vector similarity with traditional filters:

```gql
-- Vector search with metadata filters
MATCH (d:Document)
WHERE d.category = 'technology'
  AND d.published > date('2024-01-01')
  AND cosineSimilarity(d.embedding, $query_vector) > 0.7
RETURN d.title, cosineSimilarity(d.embedding, $query_vector) AS score
ORDER BY score DESC
LIMIT 10;
```

## RAG (Retrieval Augmented Generation) Pattern

Common pattern for AI applications:

```gql
-- Step 1: Retrieve relevant documents
MATCH (d:Document)
WHERE cosineSimilarity(d.embedding, $question_embedding) > 0.75
WITH d ORDER BY cosineSimilarity(d.embedding, $question_embedding) DESC
LIMIT 5

-- Step 2: Return context for LLM
RETURN collect(d.content) AS context;
```

## K-Nearest Neighbors (KNN)

Find the K most similar items:

```gql
-- Find 10 nearest neighbors
MATCH (d:Document)
WITH d, cosineSimilarity(d.embedding, $query_vector) AS similarity
ORDER BY similarity DESC
LIMIT 10
RETURN d.title, similarity;
```

## Vector Operations

### Adding Vectors

```gql
-- Combine embeddings (e.g., for mean pooling)
WITH vectorf32([0.1, 0.2, 0.3]) AS v1,
     vectorf32([0.4, 0.5, 0.6]) AS v2
RETURN vectorAdd(v1, v2) AS combined;
```

### Normalizing Vectors

```gql
-- Normalize to unit length for cosine similarity
WITH vectorf32([3, 4]) AS v
RETURN vectorNormalize(v) AS normalized;
-- Returns [0.6, 0.8]
```

### Vector Magnitude

```gql
-- Get vector length
WITH vectorf32([3, 4]) AS v
RETURN vectorMagnitude(v) AS length;
-- Returns 5.0
```

## Performance Tuning

### Index Parameters

```gql
-- High recall, slower
CREATE INDEX high_recall_idx
ON Document(embedding)
USING HNSW
OPTIONS (
    dimensions: 384,
    metric: 'cosine',
    ef_construction: 200,
    m: 32,
    ef_search: 100
);

-- Fast search, lower recall
CREATE INDEX fast_idx
ON Document(embedding)
USING HNSW
OPTIONS (
    dimensions: 384,
    metric: 'cosine',
    ef_construction: 64,
    m: 8,
    ef_search: 20
);
```

### Search Time Parameter

```gql
-- Adjust ef_search at query time for recall/speed tradeoff
SET vector_search_ef = 100;

MATCH (d:Document)
WHERE cosineSimilarity(d.embedding, $query) > 0.8
RETURN d.title;
```

## Best Practices

### 1. Choose the Right Metric

- **Cosine**: For normalized embeddings (most ML models)
- **L2**: For raw vectors, measuring actual distance
- **Inner Product**: For MIPS tasks

### 2. Dimension Considerations

```gql
-- Claimed: Support for up to 65,535 dimensions
-- Practical: Most embeddings are 384, 768, or 1536 dimensions

CREATE INDEX embedding_idx
ON Document(embedding)
USING HNSW
OPTIONS (dimensions: 1536);  -- OpenAI embedding size
```

### 3. Batch Insert for Performance

```python
# Python example - batch insert documents
documents = [...]  # List of documents with embeddings

async with client.transaction() as tx:
    for doc in documents:
        await tx.execute("""
            CREATE (:Document {
                id: $id,
                title: $title,
                embedding: vectorf32($embedding)
            })
        """, doc)
```

### 4. Use Pre-filtering When Possible

```gql
-- More efficient: filter first, then vector search
MATCH (d:Document)
WHERE d.category = 'tech'  -- Reduces search space
WITH d, cosineSimilarity(d.embedding, $query) AS score
WHERE score > 0.7
RETURN d.title, score;
```

## Practice Exercises

### Exercise 1: Document Search

1. Create 10 documents with mock embeddings (random 8D vectors)
2. Create an HNSW index
3. Search for similar documents

### Exercise 2: Recommendation System

1. Create user and product nodes with embeddings
2. Find products similar to user's preferences
3. Exclude already purchased products

## Summary

You've learned:
- Vector data types in Geode
- Creating HNSW indexes
- Similarity functions (cosine, L2, inner product)
- Semantic search patterns
- Hybrid search with filters
- RAG patterns for AI applications
- Performance tuning

Next: [Tutorial 5: Graph Algorithms](../05_graph_algorithms/)
