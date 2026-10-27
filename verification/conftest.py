"""
Pytest configuration and fixtures for Geode verification tests.

This module provides shared fixtures for connecting to Geode and
running verification tests against documented claims.
"""
import os
import json
import subprocess
import pytest
from pathlib import Path
from typing import Generator, Any, Optional
from dataclasses import dataclass


@dataclass
class QueryResult:
    """Result of a GQL query execution."""
    success: bool
    records: list
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None
    plan: Optional[dict] = None

    @property
    def record_count(self) -> int:
        return len(self.records)


class GeodeClient:
    """
    Simple Geode client for verification tests.

    Uses the geode shell CLI for query execution, which provides
    a reliable black-box testing approach.
    """

    def __init__(self, host: str = "localhost", port: int = 3141):
        self.host = host
        self.port = port
        self._docker_compose = os.environ.get("USE_DOCKER_COMPOSE", "true").lower() == "true"

    def execute(self, query: str, timeout: int = 30) -> QueryResult:
        """
        Execute a GQL query and return the result.

        Args:
            query: GQL query string
            timeout: Query timeout in seconds

        Returns:
            QueryResult with success status and records
        """
        try:
            if self._docker_compose:
                # Execute via docker compose
                cmd = [
                    "bash", str(Path(__file__).resolve().parents[1] / "scripts/geode-query.sh"),
                    query,
                ]
            else:
                # Direct execution
                cmd = [
                    "geode", "query",
                    "--server", f"{self.host}:{self.port}",
                    "--insecure",
                    query
                ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=Path(__file__).parent.parent
            )

            if result.returncode == 0:
                # Parse output - Geode shell outputs JSON lines
                records = []
                for line in result.stdout.strip().split('\n'):
                    if line and not line.startswith(('geode>', 'Connected', 'Bye')):
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            # Non-JSON output, treat as raw text
                            if line.strip():
                                records.append({"_raw": line})

                return QueryResult(success=True, records=records)
            else:
                return QueryResult(
                    success=False,
                    records=[],
                    error=result.stderr or result.stdout
                )

        except subprocess.TimeoutExpired:
            return QueryResult(
                success=False,
                records=[],
                error=f"Query timed out after {timeout} seconds"
            )
        except Exception as e:
            return QueryResult(
                success=False,
                records=[],
                error=str(e)
            )

    def execute_file(self, filepath: Path, timeout: int = 60) -> QueryResult:
        """
        Execute a GQL file.

        Args:
            filepath: Path to .gql file
            timeout: Execution timeout in seconds

        Returns:
            QueryResult with success status
        """
        query = filepath.read_text()
        return self.execute(query, timeout=timeout)

    def ping(self) -> bool:
        """Check if Geode server is responsive."""
        result = self.execute("RETURN 1", timeout=5)
        return result.success


class GeodeAdminClient(GeodeClient):
    """Extended client with administrative operations."""

    def get_config(self) -> dict:
        """Get server configuration."""
        result = self.execute("CALL db.config()")
        if result.success and result.records:
            return result.records[0] if result.records else {}
        return {}

    def get_indexes(self) -> list:
        """List all indexes."""
        result = self.execute("SHOW INDEXES")
        return result.records if result.success else []

    def get_constraints(self) -> list:
        """List all constraints."""
        result = self.execute("SHOW CONSTRAINTS")
        return result.records if result.success else []

    def clear_data(self) -> bool:
        """Clear all data (use with caution)."""
        result = self.execute("MATCH (n) DETACH DELETE n")
        return result.success


# =============================================================================
# Pytest Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def geode_host() -> str:
    """Get Geode host from environment or default."""
    return os.environ.get("GEODE_HOST", "localhost")


@pytest.fixture(scope="session")
def geode_port() -> int:
    """Get Geode port from environment or default."""
    return int(os.environ.get("GEODE_PORT", "3141"))


@pytest.fixture(scope="session")
def geode_client(geode_host: str, geode_port: int) -> Generator[GeodeClient, None, None]:
    """
    Provide a Geode client for the test session.

    This fixture creates a single client instance that is reused
    across all tests in the session.
    """
    client = GeodeClient(host=geode_host, port=geode_port)

    # Verify connectivity
    if not client.ping():
        pytest.skip("Geode server not available")

    yield client


@pytest.fixture(scope="session")
def admin_client(geode_host: str, geode_port: int) -> Generator[GeodeAdminClient, None, None]:
    """Provide an admin client for tests requiring administrative access."""
    client = GeodeAdminClient(host=geode_host, port=geode_port)

    if not client.ping():
        pytest.skip("Geode server not available")

    yield client


@pytest.fixture(scope="function")
def clean_database(admin_client: GeodeAdminClient) -> Generator[None, None, None]:
    """
    Fixture that ensures a clean database state before and after tests.

    Use this fixture for tests that need isolation.
    """
    # Clean before test
    admin_client.clear_data()

    yield

    # Clean after test
    admin_client.clear_data()


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def gql_examples_dir(project_root: Path) -> Path:
    """Get the GQL examples directory."""
    return project_root / "gql"


@pytest.fixture(scope="session")
def iso_tests_dir(project_root: Path) -> Path:
    """Get the ISO compliance tests directory."""
    return project_root / "verification" / "claims" / "compliance" / "iso_tests"


# =============================================================================
# Test Markers
# =============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "compliance: marks tests as ISO compliance tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance benchmarks"
    )
    config.addinivalue_line(
        "markers", "security: marks tests as security verification"
    )


# =============================================================================
# Test Helpers
# =============================================================================

def load_gql_file(filepath: Path) -> str:
    """Load and return contents of a GQL file."""
    return filepath.read_text()


def extract_canary_from_file(filepath: Path) -> dict:
    """
    Extract CANARY marker from a GQL or Python file.

    Returns dict with keys: REQ, FEATURE, ASPECT, STATUS
    """
    content = filepath.read_text()
    canary = {}

    import re
    match = re.search(
        r'CANARY:\s*REQ=([^;]+);\s*FEATURE="([^"]+)";\s*ASPECT=([^;]+);\s*STATUS=(\w+)',
        content
    )
    if match:
        canary = {
            'REQ': match.group(1).strip(),
            'FEATURE': match.group(2),
            'ASPECT': match.group(3).strip(),
            'STATUS': match.group(4)
        }

    return canary
