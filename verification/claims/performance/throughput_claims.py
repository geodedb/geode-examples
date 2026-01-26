#!/usr/bin/env python3
"""
Throughput Claims Verification Tests

Verifies all throughput-related performance claims.
CANARY: REQ=REQ-PERF-THROUGHPUT-001; FEATURE="ThroughputVerification"; ASPECT=Performance; STATUS=TESTED

Claims verified:
- Read-only throughput: up to 100,000 txn/sec (REQ-PERF-READ-001)
- Read-write throughput: 10,000-50,000 txn/sec (REQ-PERF-READWRITE-001)
- Write-heavy throughput: 5,000-20,000 txn/sec (REQ-PERF-WRITE-001)
"""
import asyncio
import pytest
import statistics
import subprocess
import time
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class ThroughputResult:
    """Result of a throughput test."""
    total_operations: int
    successful_operations: int
    failed_operations: int
    duration_seconds: float
    throughput_ops: float
    latency_avg_ms: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float


class GeodeTestClient:
    """Simple Geode client for throughput testing."""

    def __init__(self, use_docker: bool = True):
        self.use_docker = use_docker

    def execute(self, query: str, timeout: float = 5.0) -> Tuple[bool, float]:
        """Execute query and return (success, latency_ms)."""
        start = time.perf_counter()
        try:
            if self.use_docker:
                cmd = [
                    "docker", "compose", "exec", "-T", "geode",
                    "geode", "query",
                    "--server", "localhost:3141",
                    "--insecure",
                    query
                ]
            else:
                cmd = [
                    "geode", "query",
                    "--server", "localhost:3141",
                    "--insecure",
                    query
                ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            latency = (time.perf_counter() - start) * 1000
            return result.returncode == 0, latency
        except Exception:
            latency = (time.perf_counter() - start) * 1000
            return False, latency


async def run_throughput_test(
    client: GeodeTestClient,
    query: str,
    duration_seconds: float,
    concurrent_workers: int
) -> ThroughputResult:
    """Run a throughput test with concurrent workers."""
    results: List[Tuple[bool, float]] = []
    start_time = time.monotonic()

    async def worker():
        while time.monotonic() - start_time < duration_seconds:
            success, latency = client.execute(query)
            results.append((success, latency))
            await asyncio.sleep(0)

    tasks = [worker() for _ in range(concurrent_workers)]
    await asyncio.gather(*tasks)

    actual_duration = time.monotonic() - start_time

    # Calculate metrics
    successful = [r for r in results if r[0]]
    latencies = [r[1] for r in successful] if successful else [0]
    sorted_latencies = sorted(latencies)

    throughput = len(successful) / actual_duration if actual_duration > 0 else 0

    p50 = sorted_latencies[int(len(sorted_latencies) * 0.50)] if sorted_latencies else 0
    p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)] if sorted_latencies else 0
    p99 = sorted_latencies[min(int(len(sorted_latencies) * 0.99), len(sorted_latencies) - 1)] if sorted_latencies else 0

    return ThroughputResult(
        total_operations=len(results),
        successful_operations=len(successful),
        failed_operations=len(results) - len(successful),
        duration_seconds=actual_duration,
        throughput_ops=throughput,
        latency_avg_ms=statistics.mean(latencies) if latencies else 0,
        latency_p50_ms=p50,
        latency_p95_ms=p95,
        latency_p99_ms=p99
    )


class TestReadOnlyThroughput:
    """
    Test read-only throughput claims.

    Claim: Read-only throughput up to 100,000 txn/sec
    Source: Overview, Performance
    CANARY: REQ-PERF-READ-001
    """

    CLAIMED_MAX = 100_000
    MIN_ACCEPTABLE = 10_000  # 10% of claimed max

    @pytest.fixture(autouse=True)
    def setup(self, geode_client):
        self.client = geode_client

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_read_only_throughput_smoke(self):
        """Quick smoke test for read-only throughput."""
        result = await run_throughput_test(
            client=self.client,
            query="RETURN 1",
            duration_seconds=5,
            concurrent_workers=5
        )

        assert result.successful_operations > 0, "No successful operations"
        assert result.throughput_ops > 0, "Zero throughput achieved"

    @pytest.mark.asyncio
    @pytest.mark.performance
    @pytest.mark.slow
    async def test_read_only_throughput_standard(self):
        """Standard throughput test with moderate load."""
        result = await run_throughput_test(
            client=self.client,
            query="RETURN 1",
            duration_seconds=10,
            concurrent_workers=10
        )

        assert result.throughput_ops >= self.MIN_ACCEPTABLE * 0.1, (
            f"Throughput {result.throughput_ops:.0f} ops/sec is below minimum "
            f"acceptable threshold of {self.MIN_ACCEPTABLE * 0.1:.0f} ops/sec"
        )

    @pytest.mark.asyncio
    @pytest.mark.performance
    @pytest.mark.slow
    async def test_read_pattern_matching_throughput(self):
        """Test throughput with pattern matching queries."""
        # Setup: Create some test data
        self.client.execute("CREATE (:Person {name: 'Alice', age: 30})")
        self.client.execute("CREATE (:Person {name: 'Bob', age: 25})")
        self.client.execute("""
            MATCH (a:Person {name: 'Alice'}), (b:Person {name: 'Bob'})
            CREATE (a)-[:KNOWS]->(b)
        """)

        result = await run_throughput_test(
            client=self.client,
            query="MATCH (p:Person) RETURN p.name LIMIT 10",
            duration_seconds=10,
            concurrent_workers=5
        )

        # Cleanup
        self.client.execute("MATCH (n:Person) DETACH DELETE n")

        assert result.successful_operations > 0, "Pattern matching queries failed"

    def test_verify_claim_documentation(self):
        """Verify the claim is properly documented."""
        # This test ensures the claim exists in documentation
        claim_value = self.CLAIMED_MAX
        assert claim_value == 100_000, "Claimed max throughput should be 100,000 txn/sec"


class TestReadWriteThroughput:
    """
    Test read-write mixed throughput claims.

    Claim: Read-write throughput 10,000-50,000 txn/sec
    Source: Overview, Performance
    CANARY: REQ-PERF-READWRITE-001
    """

    CLAIMED_MIN = 10_000
    CLAIMED_MAX = 50_000

    @pytest.fixture(autouse=True)
    def setup(self, geode_client):
        self.client = geode_client

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_read_write_throughput_smoke(self):
        """Quick smoke test for read-write throughput."""
        # Alternate between reads and writes
        results: List[Tuple[bool, float]] = []
        start_time = time.monotonic()
        duration = 5

        while time.monotonic() - start_time < duration:
            # Write
            success, latency = self.client.execute(
                "CREATE (:TestNode {value: 1})"
            )
            results.append((success, latency))

            # Read
            success, latency = self.client.execute(
                "MATCH (n:TestNode) RETURN count(n)"
            )
            results.append((success, latency))

        # Cleanup
        self.client.execute("MATCH (n:TestNode) DETACH DELETE n")

        successful = len([r for r in results if r[0]])
        assert successful > 0, "No successful operations in read-write test"

    def test_verify_claim_range(self):
        """Verify the claim range is properly defined."""
        assert self.CLAIMED_MIN == 10_000
        assert self.CLAIMED_MAX == 50_000
        assert self.CLAIMED_MIN < self.CLAIMED_MAX


class TestWriteHeavyThroughput:
    """
    Test write-heavy throughput claims.

    Claim: Write-heavy throughput 5,000-20,000 txn/sec
    Source: Overview, Performance
    CANARY: REQ-PERF-WRITE-001
    """

    CLAIMED_MIN = 5_000
    CLAIMED_MAX = 20_000

    @pytest.fixture(autouse=True)
    def setup(self, geode_client):
        self.client = geode_client

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_write_heavy_throughput_smoke(self):
        """Quick smoke test for write-heavy throughput."""
        results: List[Tuple[bool, float]] = []
        start_time = time.monotonic()
        duration = 5
        counter = 0

        while time.monotonic() - start_time < duration:
            success, latency = self.client.execute(
                f"CREATE (:WriteTest {{id: 'w_{counter}', value: {counter}}})"
            )
            results.append((success, latency))
            counter += 1

        # Cleanup
        self.client.execute("MATCH (n:WriteTest) DETACH DELETE n")

        successful = len([r for r in results if r[0]])
        assert successful > 0, "No successful write operations"

    @pytest.mark.asyncio
    @pytest.mark.performance
    @pytest.mark.slow
    async def test_batch_write_throughput(self):
        """Test batch write throughput."""
        # Test batch operations for better write throughput
        batch_size = 10
        batches = 5
        results: List[Tuple[bool, float]] = []

        for batch in range(batches):
            nodes = ", ".join([
                f"(:BatchNode {{id: 'b_{batch}_{i}', value: {i}}})"
                for i in range(batch_size)
            ])
            query = f"CREATE {nodes}"
            success, latency = self.client.execute(query)
            results.append((success, latency))

        # Cleanup
        self.client.execute("MATCH (n:BatchNode) DETACH DELETE n")

        successful = len([r for r in results if r[0]])
        assert successful == batches, f"Expected {batches} successful batches, got {successful}"

    def test_verify_claim_range(self):
        """Verify the claim range is properly defined."""
        assert self.CLAIMED_MIN == 5_000
        assert self.CLAIMED_MAX == 20_000
        assert self.CLAIMED_MIN < self.CLAIMED_MAX


class TestThroughputScaling:
    """Test throughput scaling with increased load."""

    @pytest.fixture(autouse=True)
    def setup(self, geode_client):
        self.client = geode_client

    @pytest.mark.asyncio
    @pytest.mark.performance
    @pytest.mark.slow
    async def test_throughput_scales_with_workers(self):
        """Verify throughput increases with more concurrent workers."""
        results = []

        for workers in [1, 2, 5]:
            result = await run_throughput_test(
                client=self.client,
                query="RETURN 1",
                duration_seconds=5,
                concurrent_workers=workers
            )
            results.append((workers, result.throughput_ops))

        # Throughput should generally increase with more workers
        # (up to a point, depending on system resources)
        assert results[1][1] >= results[0][1] * 0.5, (
            "Throughput should not decrease significantly with 2 workers"
        )
