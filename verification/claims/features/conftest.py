#!/usr/bin/env python3
"""
Pytest configuration for feature claim verification tests.

CANARY: REQ=REQ-TEST-FEAT-001; FEATURE="FeatureTestConfig"; ASPECT=Testing; STATUS=TESTED
"""
from pathlib import Path
import os
import pytest
import subprocess
import time
from typing import Tuple, Optional


class GeodeClient:
    """Simple Geode client for feature testing."""

    def __init__(self, use_docker: bool = True):
        self.use_docker = use_docker

    def execute(self, query: str, timeout: float = 30.0, *, stdin: Optional[str] = None):
        """Execute a query and return a result object."""
        start = time.perf_counter()
        try:
            if self.use_docker:
                cmd = [
                    "bash", str(Path(__file__).resolve().parents[3] / "scripts/geode-query.sh"),
                    query,
                ]
            else:
                cmd = [
                    "geode", "query",
                    "--server", "localhost:3141",
                    "--insecure",
                    query
                ]

            result = subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=timeout)
            latency = (time.perf_counter() - start) * 1000

            return QueryResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr,
                latency_ms=latency
            )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return QueryResult(
                success=False,
                output="",
                error=str(e),
                latency_ms=latency
            )

    def execute_many(self, queries, timeout: float = 30.0):
        """Send separate statements over one authenticated batch connection."""
        queries = list(queries)
        if not queries or any("\n" in query or "\r" in query for query in queries):
            raise ValueError("Batch queries must be nonempty single-line statements")
        return self.execute("--batch", timeout=timeout, stdin="\n".join(queries) + "\n")


class QueryResult:
    """Result of a query execution."""

    def __init__(self, success: bool, output: str, error: str, latency_ms: float):
        self.success = success
        self.output = output
        self.error = error
        self.latency_ms = latency_ms


@pytest.fixture(scope="session")
def geode_client():
    """Provide a Geode client for the test session."""
    client = GeodeClient(use_docker=True)

    # Verify connection
    result = client.execute("RETURN 1")
    if not result.success:
        if os.environ.get("CI"):
            pytest.fail(f"Geode server is not available: {result.error}")
        pytest.skip("Geode server is not available")

    return client


@pytest.fixture
def clean_database(geode_client):
    """Clean up test data after each test."""
    yield geode_client

    # Cleanup common test labels
    test_labels = [
        "Person", "Document", "Article", "Location", "Device",
        "TestNode", "SearchDoc", "VectorIndexTest", "BulkVector",
        "KNNTest", "Embedding", "HighDimEmbedding"
    ]

    result = geode_client.execute_many(
        f"MATCH (n:{label}) DETACH DELETE n" for label in test_labels
    )
    assert result.success, f"Feature test cleanup failed: {result.error}"


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: mark test as slow (may be skipped in CI)"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on markers."""
    if not config.getoption("--runslow", default=False):
        skip_slow = pytest.mark.skip(reason="need --runslow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)


def pytest_addoption(parser):
    """Add custom command-line options."""
    try:
        parser.addoption(
            "--runslow",
            action="store_true",
            default=False,
            help="run slow tests"
        )
    except ValueError:
        # Option already exists
        pass
