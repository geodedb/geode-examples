#!/usr/bin/env python3
"""
Pytest configuration for performance claim verification tests.

CANARY: REQ=REQ-TEST-PERF-001; FEATURE="PerfTestConfig"; ASPECT=Testing; STATUS=TESTED
"""
import pytest
import subprocess
import time
from typing import Tuple


class GeodeClient:
    """Simple Geode client for testing."""

    def __init__(self, use_docker: bool = True):
        self.use_docker = use_docker

    def execute(self, query: str, timeout: float = 30.0) -> Tuple[bool, float]:
        """Execute a query and return (success, latency_ms)."""
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


@pytest.fixture(scope="session")
def geode_client():
    """Provide a Geode client for the test session."""
    client = GeodeClient(use_docker=True)

    # Verify connection
    success, _ = client.execute("RETURN 1")
    if not success:
        pytest.skip("Geode server is not available")

    return client


@pytest.fixture
def clean_database(geode_client):
    """Clean up test data after each test."""
    yield geode_client

    # Cleanup test data (best effort)
    test_labels = [
        "MmapTest", "ReadTest", "RandomTest", "LargeData", "BulkTest",
        "TraversalNode", "PropTest", "ConcurrentTest", "TestNode",
        "IndexTest", "RangeTest", "Person", "WriteTest", "BatchNode",
        "TestPerson"
    ]

    for label in test_labels:
        try:
            geode_client.execute(f"MATCH (n:{label}) DETACH DELETE n")
        except Exception:
            pass


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "performance: mark test as a performance test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow (may be skipped in CI)"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on markers."""
    # Skip slow tests unless explicitly requested
    if not config.getoption("--runslow", default=False):
        skip_slow = pytest.mark.skip(reason="need --runslow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)


def pytest_addoption(parser):
    """Add custom command-line options."""
    parser.addoption(
        "--runslow",
        action="store_true",
        default=False,
        help="run slow tests"
    )
