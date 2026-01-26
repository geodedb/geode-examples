"""
Pattern Matching Compliance Verification Tests

Verifies claim: All pattern matching syntax from ISO standard
Source: Features Overview
CANARY: REQ=REQ-GQL-PATTERN-001; FEATURE="PatternMatching"; ASPECT=Compliance; STATUS=TESTED

This module tests Geode's implementation of all GQL pattern matching
features as specified in ISO/IEC 39075:2024.
"""
import pytest


class TestPatternMatchingCompliance:
    """
    Verify complete pattern matching syntax from ISO standard.

    ISO/IEC 39075:2024 specifies comprehensive pattern matching
    capabilities that Geode must implement fully.
    """

    # =========================================================================
    # Node Patterns
    # =========================================================================

    @pytest.mark.compliance
    def test_anonymous_node(self, geode_client, clean_database):
        """Test anonymous node pattern ()."""
        geode_client.execute("CREATE (:Person {name: 'Alice'})")

        result = geode_client.execute("MATCH () RETURN COUNT(*) AS cnt")
        assert result.success

    @pytest.mark.compliance
    def test_labeled_node(self, geode_client, clean_database):
        """Test labeled node pattern (:Label)."""
        geode_client.execute("CREATE (:Person {name: 'Alice'})")

        result = geode_client.execute("MATCH (:Person) RETURN COUNT(*) AS cnt")
        assert result.success

    @pytest.mark.compliance
    def test_multiple_labels(self, geode_client, clean_database):
        """Test multiple labels pattern (:Label1:Label2)."""
        geode_client.execute("CREATE (:Person:Employee {name: 'Alice'})")

        result = geode_client.execute("MATCH (n:Person:Employee) RETURN n.name")
        assert result.success

    @pytest.mark.compliance
    def test_node_with_properties(self, geode_client, clean_database):
        """Test node with inline properties ({prop: value})."""
        geode_client.execute("CREATE (:Person {name: 'Alice', age: 30})")

        result = geode_client.execute("MATCH (p:Person {name: 'Alice'}) RETURN p.age")
        assert result.success

    @pytest.mark.compliance
    def test_node_variable_binding(self, geode_client, clean_database):
        """Test variable binding in node pattern (var:Label)."""
        geode_client.execute("CREATE (:Person {name: 'Alice'})")

        result = geode_client.execute("MATCH (person:Person) RETURN person.name")
        assert result.success

    # =========================================================================
    # Relationship Patterns
    # =========================================================================

    @pytest.mark.compliance
    def test_outgoing_relationship(self, geode_client, clean_database):
        """Test outgoing relationship pattern -[]->."""
        geode_client.execute("""
            CREATE (a:Person {name: 'Alice'})-[:KNOWS]->(b:Person {name: 'Bob'})
        """)

        result = geode_client.execute("""
            MATCH (a)-[]->(b) RETURN a.name, b.name
        """)
        assert result.success

    @pytest.mark.compliance
    def test_incoming_relationship(self, geode_client, clean_database):
        """Test incoming relationship pattern <-[]-."""
        geode_client.execute("""
            CREATE (a:Person {name: 'Alice'})-[:KNOWS]->(b:Person {name: 'Bob'})
        """)

        result = geode_client.execute("""
            MATCH (b)<-[]-(a) WHERE b.name = 'Bob' RETURN a.name
        """)
        assert result.success

    @pytest.mark.compliance
    def test_undirected_relationship(self, geode_client, clean_database):
        """Test undirected relationship pattern -[]-."""
        geode_client.execute("""
            CREATE (a:Person {name: 'Alice'})-[:KNOWS]->(b:Person {name: 'Bob'})
        """)

        result = geode_client.execute("""
            MATCH (a)-[]-(b) WHERE a.name = 'Bob' RETURN b.name
        """)
        assert result.success

    @pytest.mark.compliance
    def test_typed_relationship(self, geode_client, clean_database):
        """Test typed relationship pattern -[:TYPE]->."""
        geode_client.execute("""
            CREATE (a:Person {name: 'Alice'})-[:KNOWS]->(b:Person {name: 'Bob'})
        """)

        result = geode_client.execute("""
            MATCH (a)-[:KNOWS]->(b) RETURN a.name, b.name
        """)
        assert result.success

    @pytest.mark.compliance
    def test_relationship_with_properties(self, geode_client, clean_database):
        """Test relationship with properties -[:TYPE {prop: val}]->."""
        geode_client.execute("""
            CREATE (a:Person {name: 'Alice'})-[:KNOWS {since: 2020}]->(b:Person {name: 'Bob'})
        """)

        result = geode_client.execute("""
            MATCH (a)-[r:KNOWS {since: 2020}]->(b) RETURN a.name, r.since, b.name
        """)
        assert result.success

    @pytest.mark.compliance
    def test_relationship_variable(self, geode_client, clean_database):
        """Test relationship variable binding -[var:TYPE]->."""
        geode_client.execute("""
            CREATE (a:Person {name: 'Alice'})-[:KNOWS {since: 2020}]->(b:Person {name: 'Bob'})
        """)

        result = geode_client.execute("""
            MATCH (a)-[rel:KNOWS]->(b) RETURN type(rel) AS relType
        """)
        assert result.success

    @pytest.mark.compliance
    def test_multiple_relationship_types(self, geode_client, clean_database):
        """Test multiple relationship types -[:TYPE1|TYPE2]->."""
        geode_client.execute("""
            CREATE (a:Person {name: 'Alice'})-[:KNOWS]->(b:Person {name: 'Bob'}),
                   (a)-[:WORKS_WITH]->(c:Person {name: 'Carol'})
        """)

        result = geode_client.execute("""
            MATCH (a:Person {name: 'Alice'})-[:KNOWS|WORKS_WITH]->(b)
            RETURN b.name
        """)
        assert result.success

    # =========================================================================
    # Variable-Length Paths
    # =========================================================================

    @pytest.mark.compliance
    def test_variable_length_any(self, geode_client, clean_database):
        """Test unbounded variable-length path -[*]->."""
        geode_client.execute("""
            CREATE (a:Person {name: 'Alice'})-[:KNOWS]->(b:Person {name: 'Bob'})
                   -[:KNOWS]->(c:Person {name: 'Carol'})
        """)

        result = geode_client.execute("""
            MATCH (a:Person {name: 'Alice'})-[:KNOWS*]->(c)
            RETURN c.name
        """)
        assert result.success

    @pytest.mark.compliance
    def test_variable_length_exact(self, geode_client, clean_database):
        """Test exact length path -[*n]->."""
        geode_client.execute("""
            CREATE (a:Person {name: 'Alice'})-[:KNOWS]->(b:Person {name: 'Bob'})
                   -[:KNOWS]->(c:Person {name: 'Carol'})
        """)

        result = geode_client.execute("""
            MATCH (a:Person {name: 'Alice'})-[:KNOWS*2]->(c)
            RETURN c.name
        """)
        assert result.success

    @pytest.mark.compliance
    def test_variable_length_min(self, geode_client, clean_database):
        """Test minimum length path -[*n..]->."""
        geode_client.execute("""
            CREATE (a:Person {name: 'Alice'})-[:KNOWS]->(b:Person {name: 'Bob'})
                   -[:KNOWS]->(c:Person {name: 'Carol'})
        """)

        result = geode_client.execute("""
            MATCH (a:Person {name: 'Alice'})-[:KNOWS*2..]->(c)
            RETURN c.name
        """)
        assert result.success

    @pytest.mark.compliance
    def test_variable_length_max(self, geode_client, clean_database):
        """Test maximum length path -[*..n]->."""
        geode_client.execute("""
            CREATE (a:Person {name: 'Alice'})-[:KNOWS]->(b:Person {name: 'Bob'})
        """)

        result = geode_client.execute("""
            MATCH (a:Person {name: 'Alice'})-[:KNOWS*..3]->(c)
            RETURN c.name
        """)
        assert result.success

    @pytest.mark.compliance
    def test_variable_length_range(self, geode_client, clean_database):
        """Test range length path -[*n..m]->."""
        geode_client.execute("""
            CREATE (a:Person {name: 'Alice'})-[:KNOWS]->(b:Person {name: 'Bob'})
                   -[:KNOWS]->(c:Person {name: 'Carol'})
                   -[:KNOWS]->(d:Person {name: 'David'})
        """)

        result = geode_client.execute("""
            MATCH (a:Person {name: 'Alice'})-[:KNOWS*1..3]->(c)
            RETURN c.name
        """)
        assert result.success

    # =========================================================================
    # Path Patterns
    # =========================================================================

    @pytest.mark.compliance
    def test_path_binding(self, geode_client, clean_database):
        """Test path variable binding path = (a)-[]->(b)."""
        geode_client.execute("""
            CREATE (a:Person {name: 'Alice'})-[:KNOWS]->(b:Person {name: 'Bob'})
        """)

        result = geode_client.execute("""
            MATCH path = (a:Person)-[:KNOWS]->(b:Person)
            RETURN length(path) AS pathLength
        """)
        assert result.success

    @pytest.mark.compliance
    def test_path_functions(self, geode_client, clean_database):
        """Test path functions: nodes(), relationships(), length()."""
        geode_client.execute("""
            CREATE (a:Person {name: 'Alice'})-[:KNOWS]->(b:Person {name: 'Bob'})
        """)

        result = geode_client.execute("""
            MATCH path = (a:Person {name: 'Alice'})-[:KNOWS*]->(b)
            RETURN
                length(path) AS pathLen,
                [n IN nodes(path) | n.name] AS nodeNames
        """)
        assert result.success

    @pytest.mark.compliance
    def test_shortest_path(self, geode_client, clean_database):
        """Test shortestPath() function."""
        geode_client.execute("""
            CREATE (a:Person {name: 'Alice'})-[:KNOWS]->(b:Person {name: 'Bob'})
                   -[:KNOWS]->(c:Person {name: 'Carol'})
        """)

        result = geode_client.execute("""
            MATCH path = shortestPath(
                (a:Person {name: 'Alice'})-[:KNOWS*]-(c:Person {name: 'Carol'})
            )
            RETURN length(path) AS distance
        """)
        assert result.success

    # =========================================================================
    # Complex Patterns
    # =========================================================================

    @pytest.mark.compliance
    def test_chained_pattern(self, geode_client, clean_database):
        """Test chained patterns (a)-[]->(b)-[]->(c)."""
        geode_client.execute("""
            CREATE (a:Person {name: 'Alice'})-[:KNOWS]->(b:Person {name: 'Bob'})
                   -[:KNOWS]->(c:Person {name: 'Carol'})
        """)

        result = geode_client.execute("""
            MATCH (a:Person)-[:KNOWS]->(b:Person)-[:KNOWS]->(c:Person)
            RETURN a.name, b.name, c.name
        """)
        assert result.success

    @pytest.mark.compliance
    def test_divergent_pattern(self, geode_client, clean_database):
        """Test divergent patterns (a)-[]->(b), (a)-[]->(c)."""
        geode_client.execute("""
            CREATE (a:Person {name: 'Alice'})-[:KNOWS]->(b:Person {name: 'Bob'}),
                   (a)-[:KNOWS]->(c:Person {name: 'Carol'})
        """)

        result = geode_client.execute("""
            MATCH (a:Person {name: 'Alice'})-[:KNOWS]->(b),
                  (a)-[:KNOWS]->(c)
            WHERE b <> c
            RETURN b.name, c.name
        """)
        assert result.success

    @pytest.mark.compliance
    def test_convergent_pattern(self, geode_client, clean_database):
        """Test convergent patterns (a)-[]->(c), (b)-[]->(c)."""
        geode_client.execute("""
            CREATE (a:Person {name: 'Alice'})-[:KNOWS]->(c:Person {name: 'Carol'}),
                   (b:Person {name: 'Bob'})-[:KNOWS]->(c)
        """)

        result = geode_client.execute("""
            MATCH (a:Person)-[:KNOWS]->(c:Person {name: 'Carol'}),
                  (b:Person)-[:KNOWS]->(c)
            WHERE a <> b
            RETURN a.name, b.name
        """)
        assert result.success

    @pytest.mark.compliance
    def test_cycle_pattern(self, geode_client, clean_database):
        """Test cycle patterns (a)-[]->(b)-[]->(c)-[]->(a)."""
        geode_client.execute("""
            CREATE (a:Person {name: 'Alice'})-[:KNOWS]->(b:Person {name: 'Bob'})
                   -[:KNOWS]->(c:Person {name: 'Carol'})-[:KNOWS]->(a)
        """)

        result = geode_client.execute("""
            MATCH (a:Person)-[:KNOWS]->(b:Person)-[:KNOWS]->(c:Person)-[:KNOWS]->(a)
            RETURN a.name, b.name, c.name
        """)
        assert result.success

    # =========================================================================
    # Existential Subqueries
    # =========================================================================

    @pytest.mark.compliance
    def test_exists_pattern(self, geode_client, clean_database):
        """Test EXISTS pattern subquery."""
        geode_client.execute("""
            CREATE (a:Person {name: 'Alice'})-[:KNOWS]->(b:Person {name: 'Bob'}),
                   (c:Person {name: 'Carol'})
        """)

        result = geode_client.execute("""
            MATCH (p:Person)
            WHERE EXISTS { MATCH (p)-[:KNOWS]->() }
            RETURN p.name
        """)
        assert result.success

    @pytest.mark.compliance
    def test_not_exists_pattern(self, geode_client, clean_database):
        """Test NOT EXISTS pattern subquery."""
        geode_client.execute("""
            CREATE (a:Person {name: 'Alice'})-[:KNOWS]->(b:Person {name: 'Bob'}),
                   (c:Person {name: 'Carol'})
        """)

        result = geode_client.execute("""
            MATCH (p:Person)
            WHERE NOT EXISTS { MATCH (p)-[:KNOWS]->() }
            RETURN p.name
        """)
        assert result.success
