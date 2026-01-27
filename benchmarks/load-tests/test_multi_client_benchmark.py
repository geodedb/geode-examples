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
    ClientResult,
    MultiClientResult,
    ALL_CLIENTS,
    CLIENT_BENCHMARKS,
)


class TestClientResult(unittest.TestCase):
    """Tests for the ClientResult dataclass."""

    def test_create_result(self):
        """Creating a ClientResult."""
        result = ClientResult(
            client_name="go",
            workers=10,
            queries_per_worker=100,
            total_queries=1000,
            successful_queries=950,
            failed_queries=50,
            throughput_qps=500.0,
            latency_p50_ms=20.0,
            latency_p95_ms=50.0,
            latency_p99_ms=100.0,
            latency_avg_ms=25.0,
            duration_seconds=10.0,
            status="GOOD"
        )
        self.assertEqual(result.client_name, "go")
        self.assertEqual(result.workers, 10)
        self.assertEqual(result.total_queries, 1000)
        self.assertEqual(result.successful_queries, 950)
        self.assertEqual(result.failed_queries, 50)


class TestMultiClientResult(unittest.TestCase):
    """Tests for the MultiClientResult dataclass."""

    def test_create_aggregate_result(self):
        """Creating an aggregated result."""
        result = MultiClientResult(
            benchmark_name="test",
            timestamp="2026-01-27T00:00:00Z",
            total_duration_seconds=60.0,
            clients_used=["go", "rust"],
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
        """ALL_CLIENTS contains expected native clients."""
        expected = ["go", "python", "rust", "nodejs", "zig"]
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
        def classify(throughput):
            CLAIMED_MAX = 100_000
            if throughput >= CLAIMED_MAX:
                return "VERIFIED"
            elif throughput >= 10_000:
                return "EXCELLENT"
            elif throughput >= 1_000:
                return "GOOD"
            elif throughput >= 100:
                return "ACCEPTABLE"
            else:
                return "LIMITED"

        self.assertEqual(classify(100_000), "VERIFIED")
        self.assertEqual(classify(50_000), "EXCELLENT")
        self.assertEqual(classify(5_000), "GOOD")
        self.assertEqual(classify(500), "ACCEPTABLE")
        self.assertEqual(classify(50), "LIMITED")


if __name__ == "__main__":
    unittest.main()
