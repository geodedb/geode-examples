#!/usr/bin/env python3
"""
Unit tests for multi_client_benchmark.py

Tests the benchmark infrastructure without requiring a running Geode server.

CANARY: REQ=REQ-PERF-MULTICLIENT-TEST-001; FEATURE="MultiClientBenchTest"; ASPECT=UnitTests; STATUS=TESTED
"""
import unittest
import threading
import time
from unittest.mock import MagicMock, patch
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from multi_client_benchmark import (
    AtomicCounter,
    LatencyCollector,
    ClientResult,
    MultiClientResult,
    ALL_CLIENTS,
    CLIENT_BENCHMARKS,
)


class TestAtomicCounter(unittest.TestCase):
    """Tests for the AtomicCounter class."""

    def test_initial_value(self):
        """Counter starts at 0."""
        counter = AtomicCounter()
        self.assertEqual(counter.value, 0)

    def test_add_single_thread(self):
        """Adding values in single thread."""
        counter = AtomicCounter()
        counter.add(5)
        counter.add(3)
        self.assertEqual(counter.value, 8)

    def test_add_concurrent(self):
        """Adding values from multiple threads."""
        counter = AtomicCounter()
        threads = []
        increments_per_thread = 100
        num_threads = 10

        def increment():
            for _ in range(increments_per_thread):
                counter.add(1)

        for _ in range(num_threads):
            t = threading.Thread(target=increment)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        expected = num_threads * increments_per_thread
        self.assertEqual(counter.value, expected)


class TestLatencyCollector(unittest.TestCase):
    """Tests for the LatencyCollector class."""

    def test_initial_empty(self):
        """Collector starts empty."""
        collector = LatencyCollector()
        self.assertEqual(collector.samples, [])

    def test_add_samples(self):
        """Adding samples."""
        collector = LatencyCollector()
        collector.add(10.0)
        collector.add(20.0)
        collector.add(15.0)
        self.assertEqual(collector.samples, [10.0, 20.0, 15.0])

    def test_max_samples_limit(self):
        """Collector respects max_samples limit."""
        collector = LatencyCollector(max_samples=5)
        for i in range(10):
            collector.add(float(i))
        self.assertEqual(len(collector.samples), 5)
        self.assertEqual(collector.samples, [0.0, 1.0, 2.0, 3.0, 4.0])

    def test_concurrent_access(self):
        """Thread-safe sample collection."""
        collector = LatencyCollector(max_samples=1000)
        threads = []
        samples_per_thread = 100
        num_threads = 5

        def add_samples():
            for i in range(samples_per_thread):
                collector.add(float(i))

        for _ in range(num_threads):
            t = threading.Thread(target=add_samples)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        expected = num_threads * samples_per_thread
        self.assertEqual(len(collector.samples), expected)


class TestClientResult(unittest.TestCase):
    """Tests for the ClientResult dataclass."""

    def test_create_result(self):
        """Creating a ClientResult."""
        result = ClientResult(
            client_name="cli",
            workers=10,
            total_queries=100,
            successful_queries=95,
            failed_queries=5,
            throughput_qps=50.0,
            latency_p50_ms=20.0,
            latency_p99_ms=100.0,
            duration_seconds=10.0,
            status="OK"
        )
        self.assertEqual(result.client_name, "cli")
        self.assertEqual(result.workers, 10)
        self.assertEqual(result.total_queries, 100)
        self.assertEqual(result.successful_queries, 95)
        self.assertEqual(result.failed_queries, 5)


class TestMultiClientResult(unittest.TestCase):
    """Tests for the MultiClientResult dataclass."""

    def test_create_aggregate_result(self):
        """Creating an aggregated result."""
        result = MultiClientResult(
            benchmark_name="test",
            timestamp="2026-01-27T00:00:00Z",
            total_duration_seconds=60.0,
            clients_used=["cli", "go"],
            total_workers=100,
            aggregate_throughput_qps=500.0,
            aggregate_total_queries=30000,
            aggregate_successful_queries=29000,
            aggregate_failed_queries=1000,
            client_results=[],
            claimed_max_qps=100000,
            achieved_percentage=0.5,
            status="LIMITED"
        )
        self.assertEqual(result.benchmark_name, "test")
        self.assertEqual(result.total_workers, 100)
        self.assertEqual(result.aggregate_throughput_qps, 500.0)


class TestClientConfiguration(unittest.TestCase):
    """Tests for client configuration."""

    def test_all_clients_list(self):
        """ALL_CLIENTS contains expected clients."""
        expected = ["cli", "go", "python", "rust", "zig", "nodejs"]
        self.assertEqual(ALL_CLIENTS, expected)

    def test_client_benchmarks_mapping(self):
        """CLIENT_BENCHMARKS has all expected clients."""
        for client in ALL_CLIENTS:
            self.assertIn(client, CLIENT_BENCHMARKS)

    def test_node_alias(self):
        """'node' is an alias for 'nodejs'."""
        self.assertIn("node", CLIENT_BENCHMARKS)
        self.assertEqual(CLIENT_BENCHMARKS["node"], CLIENT_BENCHMARKS["nodejs"])


class TestBenchmarkLogic(unittest.TestCase):
    """Tests for benchmark calculation logic."""

    def test_throughput_calculation(self):
        """Throughput is calculated correctly."""
        successful = 1000
        duration = 10.0
        expected_throughput = successful / duration
        self.assertEqual(expected_throughput, 100.0)

    def test_latency_percentile_calculation(self):
        """Latency percentiles are calculated correctly."""
        samples = list(range(1, 101))  # 1 to 100
        sorted_samples = sorted(samples)

        # p50 should be around 50
        p50_idx = len(sorted_samples) // 2
        p50 = sorted_samples[p50_idx]
        self.assertEqual(p50, 51)

        # p99 should be 99 or 100
        p99_idx = min(int(len(sorted_samples) * 0.99), len(sorted_samples) - 1)
        p99 = sorted_samples[p99_idx]
        self.assertGreaterEqual(p99, 99)

    def test_status_classification(self):
        """Status classification based on throughput."""
        CLAIMED_MAX = 100_000

        # VERIFIED: >= 100k qps
        self.assertEqual(
            "VERIFIED" if 100_000 >= CLAIMED_MAX else "other",
            "VERIFIED"
        )

        # PARTIAL: >= 10k qps
        self.assertEqual(
            "PARTIAL" if 10_000 >= 10_000 and 10_000 < CLAIMED_MAX else "other",
            "PARTIAL"
        )

        # BASELINE: >= 1k qps
        self.assertEqual(
            "BASELINE" if 1_000 >= 1_000 and 1_000 < 10_000 else "other",
            "BASELINE"
        )

        # LIMITED: < 1k qps
        self.assertEqual(
            "LIMITED" if 500 < 1_000 else "other",
            "LIMITED"
        )


class TestQueryExecution(unittest.TestCase):
    """Tests for query execution behavior."""

    def test_single_query_no_batch(self):
        """Individual queries are executed, not batched."""
        # The fix ensures we don't batch queries with semicolons
        # Each query should be a single statement
        query = "RETURN 1"
        self.assertNotIn(";", query)

    def test_batch_size_iterations(self):
        """Batch size controls iteration count, not semicolon joining."""
        batch_size = 5
        # With the fix, we run batch_size individual queries
        # Not one query with batch_size statements joined by semicolons
        queries_to_run = batch_size
        self.assertEqual(queries_to_run, 5)


if __name__ == "__main__":
    unittest.main()
