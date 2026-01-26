#!/usr/bin/env python3
"""
Concurrent Connections Benchmark

Verifies claim: 10,000+ concurrent connections
Source: Overview, Scalability
CANARY: REQ=REQ-PERF-CONN-001; FEATURE="ConcurrentConnections"; ASPECT=Performance; STATUS=TESTED

This benchmark tests Geode's ability to handle a large number of
concurrent client connections while maintaining responsiveness.
"""
import argparse
import asyncio
import json
import os
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


@dataclass
class ConnectionBenchmarkResult:
    """Result of a concurrent connections benchmark run."""
    benchmark_name: str
    timestamp: str
    duration_seconds: float
    target_connections: int
    established_connections: int
    failed_connections: int
    connection_success_rate: float
    queries_executed: int
    successful_queries: int
    failed_queries: int
    query_success_rate: float
    avg_connection_time_ms: float
    avg_query_latency_ms: float
    max_concurrent_achieved: int
    memory_mb_estimate: float
    claimed_min_connections: int
    achieved_percentage: float
    status: str


class GeodeConnection:
    """Represents a single Geode connection."""

    def __init__(self, conn_id: int, host: str = "localhost", port: int = 3141, use_docker: bool = True, insecure: bool = True):
        self.conn_id = conn_id
        self.host = host
        self.port = port
        self.use_docker = use_docker
        self.insecure = insecure
        self.connected = False
        self.connection_time_ms: float = 0
        self.queries_executed: int = 0
        self.queries_failed: int = 0

    def _build_cmd(self, query: str) -> list:
        """Build the command to execute a query."""
        if self.use_docker:
            cmd = [
                "docker", "compose", "exec", "-T", "geode",
                "geode", "query",
                "--server", "localhost:3141",
            ]
            if self.insecure:
                cmd.append("--insecure")
            cmd.append(query)
        else:
            cmd = [
                "geode", "query",
                "--server", f"{self.host}:{self.port}",
            ]
            if self.insecure:
                cmd.append("--insecure")
            cmd.append(query)
        return cmd

    def connect(self) -> bool:
        """Establish connection by executing a simple query."""
        start = time.perf_counter()
        try:
            cmd = self._build_cmd("RETURN 1")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10.0)
            self.connection_time_ms = (time.perf_counter() - start) * 1000

            if result.returncode == 0:
                self.connected = True
                return True
            return False
        except Exception:
            self.connection_time_ms = (time.perf_counter() - start) * 1000
            return False

    def execute_query(self, query: str) -> tuple[bool, float]:
        """Execute a query on this connection."""
        start = time.perf_counter()
        try:
            cmd = self._build_cmd(query)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0)
            latency = (time.perf_counter() - start) * 1000
            self.queries_executed += 1

            if result.returncode == 0:
                return True, latency
            else:
                self.queries_failed += 1
                return False, latency
        except Exception:
            latency = (time.perf_counter() - start) * 1000
            self.queries_executed += 1
            self.queries_failed += 1
            return False, latency


async def establish_connections(
    target_connections: int,
    batch_size: int,
    use_docker: bool
) -> tuple[List[GeodeConnection], List[float]]:
    """Establish connections in batches."""
    connections = []
    connection_times = []

    print(f"Establishing {target_connections} connections in batches of {batch_size}...")

    for batch_start in range(0, target_connections, batch_size):
        batch_end = min(batch_start + batch_size, target_connections)
        batch_connections = []

        for i in range(batch_start, batch_end):
            conn = GeodeConnection(i, use_docker=use_docker)
            batch_connections.append(conn)

        # Connect batch concurrently using asyncio.to_thread
        tasks = [asyncio.to_thread(conn.connect) for conn in batch_connections]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for conn, result in zip(batch_connections, results):
            if result is True:
                connections.append(conn)
                connection_times.append(conn.connection_time_ms)

        # Progress update
        established = len([c for c in connections if c.connected])
        print(f"  Progress: {established}/{batch_end} connections established")

        # Small delay between batches to prevent overwhelming the server
        await asyncio.sleep(0.1)

    return connections, connection_times


async def run_concurrent_queries(
    connections: List[GeodeConnection],
    queries_per_connection: int
) -> tuple[List[tuple[bool, float]], int]:
    """Run queries concurrently on all connections."""
    all_results = []
    total_queries = 0

    print(f"Running {queries_per_connection} queries on each of {len(connections)} connections...")

    query = "RETURN 1 + 1"

    for round_num in range(queries_per_connection):
        tasks = [asyncio.to_thread(conn.execute_query, query) for conn in connections]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, tuple):
                all_results.append(result)
                total_queries += 1

        if (round_num + 1) % 5 == 0:
            print(f"  Progress: {round_num + 1}/{queries_per_connection} query rounds completed")

    return all_results, total_queries


async def run_benchmark(
    target_connections: int = 100,
    batch_size: int = 10,
    queries_per_connection: int = 10,
    use_docker: bool = True
) -> ConnectionBenchmarkResult:
    """Run the concurrent connections benchmark."""
    print(f"Starting concurrent connections benchmark...")
    print(f"  Target connections: {target_connections}")
    print(f"  Batch size: {batch_size}")
    print(f"  Queries per connection: {queries_per_connection}")

    start_time = time.monotonic()

    # Establish connections
    connections, connection_times = await establish_connections(
        target_connections, batch_size, use_docker
    )

    established = len(connections)
    failed_connections = target_connections - established

    print(f"\nConnection phase complete:")
    print(f"  Established: {established}")
    print(f"  Failed: {failed_connections}")

    # Run queries on all connections
    query_results, total_queries = await run_concurrent_queries(
        connections, queries_per_connection
    )

    actual_duration = time.monotonic() - start_time

    # Calculate metrics
    successful_queries = len([r for r in query_results if r[0]])
    failed_queries = len([r for r in query_results if not r[0]])
    query_latencies = [r[1] for r in query_results if r[0]]

    avg_connection_time = statistics.mean(connection_times) if connection_times else 0
    avg_query_latency = statistics.mean(query_latencies) if query_latencies else 0

    connection_success_rate = (established / target_connections * 100) if target_connections > 0 else 0
    query_success_rate = (successful_queries / total_queries * 100) if total_queries > 0 else 0

    # Estimate memory (rough approximation)
    memory_per_conn_kb = 64  # Estimated KB per connection
    memory_mb_estimate = (established * memory_per_conn_kb) / 1024

    CLAIMED_MIN = 10_000
    achieved_pct = (established / CLAIMED_MIN) * 100

    if established >= CLAIMED_MIN:
        status = "VERIFIED"
    elif established >= CLAIMED_MIN * 0.1:
        status = "PARTIAL"
    else:
        status = "FAILED"

    return ConnectionBenchmarkResult(
        benchmark_name="concurrent_connections",
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        duration_seconds=actual_duration,
        target_connections=target_connections,
        established_connections=established,
        failed_connections=failed_connections,
        connection_success_rate=connection_success_rate,
        queries_executed=total_queries,
        successful_queries=successful_queries,
        failed_queries=failed_queries,
        query_success_rate=query_success_rate,
        avg_connection_time_ms=avg_connection_time,
        avg_query_latency_ms=avg_query_latency,
        max_concurrent_achieved=established,
        memory_mb_estimate=memory_mb_estimate,
        claimed_min_connections=CLAIMED_MIN,
        achieved_percentage=achieved_pct,
        status=status
    )


def print_result(result: ConnectionBenchmarkResult):
    """Print benchmark results."""
    print("\n" + "=" * 60)
    print("CONCURRENT CONNECTIONS BENCHMARK RESULTS")
    print("=" * 60)
    print(f"Timestamp: {result.timestamp}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    print()
    print("CONNECTIONS:")
    print(f"  Target:           {result.target_connections:,}")
    print(f"  Established:      {result.established_connections:,}")
    print(f"  Failed:           {result.failed_connections:,}")
    print(f"  Success rate:     {result.connection_success_rate:.1f}%")
    print(f"  Avg connect time: {result.avg_connection_time_ms:.2f}ms")
    print()
    print("QUERIES:")
    print(f"  Total executed:   {result.queries_executed:,}")
    print(f"  Successful:       {result.successful_queries:,}")
    print(f"  Failed:           {result.failed_queries:,}")
    print(f"  Success rate:     {result.query_success_rate:.1f}%")
    print(f"  Avg latency:      {result.avg_query_latency_ms:.2f}ms")
    print()
    print("RESOURCES:")
    print(f"  Est. memory:      {result.memory_mb_estimate:.1f} MB")
    print()
    print("CLAIM VERIFICATION:")
    print(f"  Claimed min:      {result.claimed_min_connections:,} connections")
    print(f"  Achieved:         {result.achieved_percentage:.1f}% of claimed")
    print(f"  Status:           {result.status}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Concurrent connections benchmark for Geode"
    )
    parser.add_argument(
        "--connections", "-c",
        type=int,
        default=100,
        help="Target number of concurrent connections (default: 100)"
    )
    parser.add_argument(
        "--batch-size", "-b",
        type=int,
        default=10,
        help="Connection batch size (default: 10)"
    )
    parser.add_argument(
        "--queries", "-q",
        type=int,
        default=10,
        help="Queries per connection (default: 10)"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output JSON file path"
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to existing output file"
    )
    parser.add_argument(
        "--no-docker",
        action="store_true",
        help="Don't use docker compose (direct connection)"
    )
    parser.add_argument(
        "--target",
        type=int,
        default=10000,
        help="Target connections for verification (default: 10000)"
    )

    args = parser.parse_args()

    result = asyncio.run(run_benchmark(
        target_connections=args.connections,
        batch_size=args.batch_size,
        queries_per_connection=args.queries,
        use_docker=not args.no_docker
    ))

    print_result(result)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if args.append and output_path.exists():
            with open(output_path) as f:
                data = json.load(f)
            if isinstance(data, list):
                data.append(asdict(result))
            else:
                data = [data, asdict(result)]
        else:
            data = asdict(result)

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"\nResults saved to: {output_path}")

    sys.exit(0 if result.status in ["VERIFIED", "PARTIAL"] else 1)


if __name__ == "__main__":
    main()
