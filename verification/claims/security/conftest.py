#!/usr/bin/env python3
"""
Pytest configuration for security claim verification tests.

CANARY: REQ=REQ-TEST-SEC-001; FEATURE="SecurityTestConfig"; ASPECT=Testing; STATUS=TESTED
"""
import pytest
import subprocess
import time
from typing import Tuple


class GeodeClient:
    """Simple Geode client for security testing."""

    def __init__(self, use_docker: bool = True):
        self.use_docker = use_docker

    def execute(self, query: str, timeout: float = 30.0):
        """Execute a query and return a result object."""
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
        pytest.skip("Geode server is not available")

    return client


@pytest.fixture
def clean_database(geode_client):
    """Clean up test data after each test."""
    yield geode_client

    # Cleanup common test labels
    test_labels = [
        "SensitiveData", "LargeData", "BinaryTest", "TransparentTest", "PerfTest",
        "Document", "Report", "Project", "ClassifiedDoc", "TeamData",
        "TenantData", "OrgUnit", "OrgData",
        "AuditTest", "AuditableData", "UserData", "HealthRecord", "FinancialTransaction",
        "TrackedRecord", "ChangeLog", "SensitiveResource", "AccessLog"
    ]

    for label in test_labels:
        try:
            geode_client.execute(f"MATCH (n:{label}) DETACH DELETE n")
        except Exception:
            pass


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: mark test as slow (may be skipped in CI)"
    )
    config.addinivalue_line(
        "markers", "security: mark test as security-related"
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
        pass
