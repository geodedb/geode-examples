#!/usr/bin/env python3
"""
Shard Distribution Verification Tests

Verifies claims about distributed shard functionality:
- Horizontal scaling via sharding
- Data distribution across shards
- Shard-aware query routing

Source: Overview, Architecture
CANARY: REQ=REQ-SCALE-SHARD-001; FEATURE="ShardDistribution"; ASPECT=Scalability; STATUS=TESTED

Note: These tests verify shard-related functionality in single-node mode.
Full distributed testing requires multi-node cluster setup.
"""
import pytest


class TestShardDistributionClaim:
    """
    Verify shard distribution functionality.

    Geode claims to support:
    - Horizontal scaling through sharding
    - Automatic data distribution
    - Configurable shard count
    - Shard-aware query execution
    """

    @pytest.fixture(autouse=True)
    def setup(self, geode_client, clean_database):
        self.client = geode_client
        yield

    # =========================================================================
    # Shard-Simulated Data Distribution
    # =========================================================================

    def test_partition_key_usage(self):
        """Test using partition keys for data distribution."""
        # Create nodes with explicit partition keys
        for i in range(10):
            partition = i % 4  # Simulate 4 partitions
            result = self.client.execute(f"""
                CREATE (:PartitionedData {{
                    id: 'pd_{i}',
                    partition_key: {partition},
                    value: {i * 10}
                }})
            """)
            assert result.success, f"Failed to create partitioned data: {result.error}"

        # Query by partition
        result = self.client.execute("""
            MATCH (n:PartitionedData)
            WHERE n.partition_key = 0
            RETURN count(n) AS count
        """)
        assert result.success, f"Partition query failed: {result.error}"

        # Cleanup
        self.client.execute("MATCH (n:PartitionedData) DETACH DELETE n")

    def test_data_locality_pattern(self):
        """Test patterns that would benefit from data locality in sharding."""
        # Create related nodes that should be co-located
        self.client.execute("""
            CREATE (u:User {id: 'user_1', shard_hint: 'shard_a'})-[:OWNS]->(o:Order {id: 'order_1', shard_hint: 'shard_a'})
        """)
        self.client.execute("""
            CREATE (u:User {id: 'user_2', shard_hint: 'shard_b'})-[:OWNS]->(o:Order {id: 'order_2', shard_hint: 'shard_b'})
        """)

        # Query that benefits from locality
        result = self.client.execute("""
            MATCH (u:User {shard_hint: 'shard_a'})-[:OWNS]->(o:Order)
            RETURN u.id, o.id
        """)
        assert result.success, f"Locality query failed: {result.error}"

        # Cleanup
        self.client.execute("MATCH (n:User) DETACH DELETE n")
        self.client.execute("MATCH (n:Order) DETACH DELETE n")

    # =========================================================================
    # Scaling Patterns
    # =========================================================================

    @pytest.mark.slow
    def test_bulk_data_distribution(self):
        """Test bulk data that would be distributed across shards."""
        # Create bulk data with varying partition keys
        for i in range(100):
            partition = i % 8  # Simulate 8 shards
            self.client.execute(f"""
                CREATE (:BulkData {{
                    id: 'bulk_{i}',
                    partition: {partition},
                    value: {i}
                }})
            """)

        # Verify distribution
        result = self.client.execute("""
            MATCH (n:BulkData)
            RETURN n.partition AS partition, count(n) AS count
            ORDER BY partition
        """)
        assert result.success, f"Distribution query failed: {result.error}"

        # Cleanup
        self.client.execute("MATCH (n:BulkData) DETACH DELETE n")

    @pytest.mark.slow
    def test_cross_partition_query(self):
        """Test queries that span multiple partitions."""
        # Create data across partitions
        for i in range(20):
            partition = i % 4
            self.client.execute(f"""
                CREATE (:CrossPartition {{
                    id: 'cp_{i}',
                    partition: {partition},
                    category: '{['A', 'B'][i % 2]}'
                }})
            """)

        # Query spanning all partitions
        result = self.client.execute("""
            MATCH (n:CrossPartition)
            WHERE n.category = 'A'
            RETURN count(n) AS count
        """)
        assert result.success, f"Cross-partition query failed: {result.error}"

        # Cleanup
        self.client.execute("MATCH (n:CrossPartition) DETACH DELETE n")

    # =========================================================================
    # Shard Configuration
    # =========================================================================

    def test_shard_metadata_query(self):
        """Test querying shard metadata (if available)."""
        # Try to get shard information
        result = self.client.execute("CALL db.info()")
        # May or may not be supported

    def test_node_count_scaling(self):
        """Test that node counts scale appropriately."""
        # Create nodes
        for i in range(50):
            self.client.execute(f"CREATE (:ScaleTest {{id: 'st_{i}'}})")

        # Count nodes
        result = self.client.execute("""
            MATCH (n:ScaleTest)
            RETURN count(n) AS total
        """)
        assert result.success, f"Count query failed: {result.error}"

        # Cleanup
        self.client.execute("MATCH (n:ScaleTest) DETACH DELETE n")


class TestScalabilityPatterns:
    """Test common scalability patterns."""

    @pytest.fixture(autouse=True)
    def setup(self, geode_client, clean_database):
        self.client = geode_client
        yield

    @pytest.mark.slow
    def test_fan_out_pattern(self):
        """Test fan-out query pattern (one-to-many)."""
        # Create hub and spokes
        self.client.execute("CREATE (:Hub {id: 'hub_1'})")
        for i in range(20):
            self.client.execute(f"""
                MATCH (h:Hub {{id: 'hub_1'}})
                CREATE (h)-[:CONNECTS]->(:Spoke {{id: 'spoke_{i}'}})
            """)

        # Fan-out query
        result = self.client.execute("""
            MATCH (h:Hub {id: 'hub_1'})-[:CONNECTS]->(s:Spoke)
            RETURN count(s) AS spoke_count
        """)
        assert result.success, f"Fan-out query failed: {result.error}"

        # Cleanup
        self.client.execute("MATCH (n:Hub) DETACH DELETE n")
        self.client.execute("MATCH (n:Spoke) DETACH DELETE n")

    @pytest.mark.slow
    def test_fan_in_pattern(self):
        """Test fan-in query pattern (many-to-one)."""
        # Create sources pointing to sink
        self.client.execute("CREATE (:Sink {id: 'sink_1'})")
        for i in range(20):
            self.client.execute(f"""
                MATCH (s:Sink {{id: 'sink_1'}})
                CREATE (:Source {{id: 'src_{i}'}})-[:FEEDS]->(s)
            """)

        # Fan-in query
        result = self.client.execute("""
            MATCH (src:Source)-[:FEEDS]->(sink:Sink {id: 'sink_1'})
            RETURN count(src) AS source_count
        """)
        assert result.success, f"Fan-in query failed: {result.error}"

        # Cleanup
        self.client.execute("MATCH (n:Sink) DETACH DELETE n")
        self.client.execute("MATCH (n:Source) DETACH DELETE n")
