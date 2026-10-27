#!/usr/bin/env python3
"""
Vector Search Feature Verification Tests

Verifies claim: HNSW vector index for similarity search
Source: Features Overview, Performance
CANARY: REQ=REQ-VECTOR-001; FEATURE="VectorSearch"; ASPECT=Features; STATUS=TESTED

This module verifies Geode's vector search capabilities including
HNSW indexing, similarity functions, and vector operations.
"""
import json
import pytest
import random


class TestVectorSearchClaim:
    """
    Verify claim: Vector/HNSW index for similarity search.

    Geode claims to support:
    - HNSW (Hierarchical Navigable Small World) vector index
    - Multiple distance functions (cosine, euclidean, dot product)
    - High-dimensional vector storage (up to 1024+ dimensions)
    - Sub-millisecond similarity search
    """

    @pytest.fixture(autouse=True)
    def setup(self, geode_client, clean_database):
        self.client = geode_client
        yield

    # =========================================================================
    # Vector Creation and Storage
    # =========================================================================

    def test_vector_property_creation(self):
        """Test creating nodes with vector properties."""
        # Create a node with a vector property
        result = self.client.execute("""
            CREATE (:Document {
                id: 'doc1',
                title: 'Test Document',
                embedding: [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
            })
        """)
        assert result.success, f"Vector property creation failed: {result.error}"

        # Verify retrieval
        result = self.client.execute("""
            MATCH (d:Document {id: 'doc1'})
            RETURN d.embedding AS vector
        """)
        assert result.success, f"Vector retrieval failed: {result.error}"

        # Cleanup
        self.client.execute("MATCH (d:Document) DETACH DELETE d")

    def test_high_dimensional_vectors(self):
        """Test storing high-dimensional vectors (128D)."""
        # Generate 128-dimensional vector
        vector = [round(random.random(), 4) for _ in range(128)]
        vector_str = "[" + ", ".join(str(v) for v in vector) + "]"

        result = self.client.execute(f"""
            CREATE (:Embedding {{
                id: 'emb_128d',
                vector: {vector_str}
            }})
        """)
        assert result.success, f"128D vector creation failed: {result.error}"

        # Cleanup
        self.client.execute("MATCH (e:Embedding) DETACH DELETE e")

    def test_very_high_dimensional_vectors(self):
        """Test storing very high-dimensional vectors (512D)."""
        # Generate 512-dimensional vector
        vector = [round(random.random(), 4) for _ in range(512)]
        vector_str = "[" + ", ".join(str(v) for v in vector) + "]"

        result = self.client.execute(f"""
            CREATE (:HighDimEmbedding {{
                id: 'emb_512d',
                vector: {vector_str}
            }})
        """)
        assert result.success, f"512D vector creation failed: {result.error}"

        # Cleanup
        self.client.execute("MATCH (e:HighDimEmbedding) DETACH DELETE e")

    # =========================================================================
    # Distance Functions
    # =========================================================================

    def test_euclidean_distance(self):
        """Test Euclidean (L2) distance calculation."""
        v1 = "[1.0, 0.0, 0.0, 0.0]"
        v2 = "[0.0, 1.0, 0.0, 0.0]"

        # sqrt(2) = 1.414...
        result = self.client.execute(f"""
            WITH {v1} AS v1, {v2} AS v2
            RETURN vector_l2(vectorf32(v1), vectorf32(v2)) AS euclidean_distance
        """)
        assert result.success, f"Euclidean distance failed: {result.error}"
        distance = json.loads(result.output)["rows"][0]["euclidean_distance"]
        assert float(distance) == pytest.approx(2 ** 0.5, abs=1e-6)

    def test_cosine_similarity(self):
        """Test cosine similarity calculation."""
        v1 = "[1.0, 0.0, 0.0]"
        v2 = "[1.0, 0.0, 0.0]"  # Same direction = similarity 1.0

        result = self.client.execute(f"""
            WITH {v1} AS v1, {v2} AS v2
            RETURN vector_cosine(vectorf32(v1), vectorf32(v2)) AS cosine_similarity
        """)
        assert result.success, f"Cosine similarity failed: {result.error}"
        similarity = json.loads(result.output)["rows"][0]["cosine_similarity"]
        assert float(similarity) == pytest.approx(1.0)

    def test_dot_product(self):
        """Test dot product calculation."""
        v1 = "[1.0, 2.0, 3.0]"
        v2 = "[4.0, 5.0, 6.0]"
        # Expected: 1*4 + 2*5 + 3*6 = 4 + 10 + 18 = 32

        result = self.client.execute(f"""
            WITH {v1} AS v1, {v2} AS v2
            RETURN vector_dot(vectorf32(v1), vectorf32(v2)) AS dot_product
        """)
        assert result.success, f"Dot product failed: {result.error}"
        dot_product = json.loads(result.output)["rows"][0]["dot_product"]
        assert float(dot_product) == pytest.approx(32.0)

    def test_manhattan_distance(self):
        """Test Manhattan (L1) distance calculation."""
        v1 = "[1.0, 2.0, 3.0]"
        v2 = "[4.0, 6.0, 8.0]"
        # Expected: |1-4| + |2-6| + |3-8| = 3 + 4 + 5 = 12

        result = self.client.execute(f"""
            WITH {v1} AS v1, {v2} AS v2
            RETURN manhattan(vectorf32(v1), vectorf32(v2)) AS manhattan_distance
        """)
        assert result.success, f"Manhattan distance failed: {result.error}"
        distance = json.loads(result.output)["rows"][0]["manhattan_distance"]
        assert float(distance) == pytest.approx(12.0)

    # =========================================================================
    # Similarity Search
    # =========================================================================

    @pytest.mark.slow
    def test_similarity_search_workflow(self):
        """Test end-to-end similarity search workflow."""
        # Create documents with embeddings
        documents = [
            ("doc1", "Machine learning basics", [0.9, 0.1, 0.0, 0.0]),
            ("doc2", "Deep learning networks", [0.8, 0.2, 0.1, 0.0]),
            ("doc3", "Natural language processing", [0.7, 0.3, 0.2, 0.1]),
            ("doc4", "Computer graphics", [0.1, 0.8, 0.1, 0.0]),
            ("doc5", "Database systems", [0.2, 0.1, 0.8, 0.1]),
        ]

        for doc_id, title, embedding in documents:
            emb_str = "[" + ", ".join(str(v) for v in embedding) + "]"
            self.client.execute(f"""
                CREATE (:SearchDoc {{
                    id: '{doc_id}',
                    title: '{title}',
                    embedding: {emb_str}
                }})
            """)

        # Search for similar documents to a query vector
        query_vector = "[0.85, 0.15, 0.05, 0.0]"  # Similar to ML/DL documents

        result = self.client.execute(f"""
            WITH {query_vector} AS query
            MATCH (d:SearchDoc)
            WITH d, d.embedding AS emb, query
            WITH d,
                vector_dot(vectorf32(query), vectorf32(emb)) AS similarity
            RETURN d.title, similarity
            ORDER BY similarity DESC
            LIMIT 3
        """)
        assert result.success, f"Similarity search failed: {result.error}"

        # Cleanup
        self.client.execute("MATCH (d:SearchDoc) DETACH DELETE d")

    # =========================================================================
    # Vector Index (HNSW)
    # =========================================================================

    @pytest.mark.slow
    def test_vector_index_creation(self):
        """Test creating HNSW vector index."""
        # First create some data
        for i in range(10):
            vector = [round(random.random(), 4) for _ in range(8)]
            vector_str = "[" + ", ".join(str(v) for v in vector) + "]"
            self.client.execute(f"""
                CREATE (:VectorIndexTest {{
                    id: 'vit_{i}',
                    embedding: {vector_str}
                }})
            """)

        # Try to create vector index
        result = self.client.execute("""
            CREATE INDEX vec_idx ON VectorIndexTest(embedding) USING vector
        """)
        assert result.success, f"Vector index creation failed: {result.error}"

        # Cleanup
        self.client.execute("DROP INDEX vec_idx")
        self.client.execute("MATCH (v:VectorIndexTest) DETACH DELETE v")

    # =========================================================================
    # Vector Operations
    # =========================================================================

    def test_vector_normalization(self):
        """Test vector normalization for unit vectors."""
        v = "[3.0, 4.0]"  # Magnitude = 5, normalized = [0.6, 0.8]

        result = self.client.execute(f"""
            WITH {v} AS v
            WITH v, sqrt(vector_dot(vectorf32(v), vectorf32(v))) AS magnitude
            RETURN [x IN v | x / magnitude] AS normalized
        """)
        assert result.success, f"Vector normalization failed: {result.error}"
        normalized = json.loads(result.output)["rows"][0]["normalized"]
        assert [float(value) for value in normalized] == pytest.approx([0.6, 0.8])

    def test_vector_addition(self):
        """Test vector addition."""
        v1 = "[1.0, 2.0, 3.0]"
        v2 = "[4.0, 5.0, 6.0]"

        result = self.client.execute(f"""
            WITH {v1} AS v1, {v2} AS v2
            RETURN [i IN range(0, size(v1)) | v1[i] + v2[i]] AS sum_vector
        """)
        assert result.success, f"Vector addition failed: {result.error}"
        values = json.loads(result.output)["rows"][0]["sum_vector"]
        assert [float(value) for value in values] == pytest.approx([5.0, 7.0, 9.0])

    def test_vector_scaling(self):
        """Test vector scalar multiplication."""
        v = "[1.0, 2.0, 3.0]"
        scalar = 2.0

        result = self.client.execute(f"""
            WITH {v} AS v, {scalar} AS scalar
            RETURN [x IN v | x * scalar] AS scaled_vector
        """)
        assert result.success, f"Vector scaling failed: {result.error}"
        values = json.loads(result.output)["rows"][0]["scaled_vector"]
        assert [float(value) for value in values] == pytest.approx([2.0, 4.0, 6.0])


class TestVectorSearchPerformance:
    """Performance-focused tests for vector search."""

    @pytest.fixture(autouse=True)
    def setup(self, geode_client, clean_database):
        self.client = geode_client
        yield

    @pytest.mark.slow
    def test_bulk_vector_insertion(self):
        """Test inserting many vectors efficiently."""
        vectors_created = 0

        for i in range(100):
            vector = [round(random.random(), 4) for _ in range(32)]
            vector_str = "[" + ", ".join(str(v) for v in vector) + "]"

            result = self.client.execute(f"""
                CREATE (:BulkVector {{
                    id: 'bv_{i}',
                    embedding: {vector_str}
                }})
            """)
            if result.success:
                vectors_created += 1

        assert vectors_created >= 90, f"Expected 90+ vectors, created {vectors_created}"

        # Cleanup
        self.client.execute("MATCH (v:BulkVector) DETACH DELETE v")

    @pytest.mark.slow
    def test_knn_search_pattern(self):
        """Test k-nearest neighbors search pattern."""
        # Create test vectors
        for i in range(50):
            vector = [round(random.random(), 4) for _ in range(16)]
            vector_str = "[" + ", ".join(str(v) for v in vector) + "]"
            self.client.execute(f"""
                CREATE (:KNNTest {{
                    id: 'knn_{i}',
                    embedding: {vector_str}
                }})
            """)

        # Query vector
        query = [round(random.random(), 4) for _ in range(16)]
        query_str = "[" + ", ".join(str(v) for v in query) + "]"

        # Find k=5 nearest neighbors
        result = self.client.execute(f"""
            WITH {query_str} AS query
            MATCH (n:KNNTest)
            RETURN n.id, vector_l2(vectorf32(query), vectorf32(n.embedding)) AS distance
            ORDER BY distance
            LIMIT 5
        """)
        assert result.success, f"KNN search failed: {result.error}"

        # Cleanup
        self.client.execute("MATCH (n:KNNTest) DETACH DELETE n")
