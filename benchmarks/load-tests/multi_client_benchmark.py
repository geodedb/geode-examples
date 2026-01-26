#!/usr/bin/env python3
"""
Multi-Client High-Throughput Benchmark for Geode

This benchmark runs multiple client implementations in parallel to achieve
maximum throughput. Each client type uses subprocess-based execution to
query the Geode server.

Note: This benchmark uses subprocess calls to the geode CLI for all client types.
For true native client benchmarks, use the actual client libraries from their
respective repositories (geode-client-go, geode-client-rust, etc.).

CANARY: REQ=REQ-PERF-MULTICLIENT-001; FEATURE="MultiClientBench"; ASPECT=Performance; STATUS=TESTED

Usage:
    # Run with all available clients
    python benchmarks/load-tests/multi_client_benchmark.py --clients all

    # Run with specific clients
    python benchmarks/load-tests/multi_client_benchmark.py --clients cli,go,python

    # High-scale test with 100 workers per client
    python benchmarks/load-tests/multi_client_benchmark.py --clients cli,go --workers 100 --duration 120
"""
import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass
class ClientResult:
    """Result from a single client benchmark."""
    client_name: str
    workers: int
    total_queries: int
    successful_queries: int
    failed_queries: int
    throughput_qps: float
    latency_p50_ms: float
    latency_p99_ms: float
    duration_seconds: float
    status: str


@dataclass
class MultiClientResult:
    """Aggregated result from multi-client benchmark."""
    benchmark_name: str
    timestamp: str
    total_duration_seconds: float
    clients_used: List[str]
    total_workers: int
    aggregate_throughput_qps: float
    aggregate_total_queries: int
    aggregate_successful_queries: int
    aggregate_failed_queries: int
    client_results: List[Dict]
    claimed_max_qps: int
    achieved_percentage: float
    status: str


class AtomicCounter:
    """Thread-safe counter."""
    def __init__(self):
        self._value = 0
        self._lock = threading.Lock()

    def add(self, n: int):
        with self._lock:
            self._value += n

    @property
    def value(self):
        with self._lock:
            return self._value


class LatencyCollector:
    """Thread-safe latency collector."""
    def __init__(self, max_samples: int = 50000):
        self._samples = []
        self._lock = threading.Lock()
        self._max_samples = max_samples

    def add(self, latency_ms: float):
        with self._lock:
            if len(self._samples) < self._max_samples:
                self._samples.append(latency_ms)

    @property
    def samples(self):
        with self._lock:
            return list(self._samples)


# =============================================================================
# Base Worker Function (used by all client types)
# =============================================================================

def base_worker(
    worker_id: int,
    stop_event: threading.Event,
    successful: AtomicCounter,
    failed: AtomicCounter,
    latencies: LatencyCollector,
    batch_size: int,
    host: str,
    port: int,
    use_docker: bool,
    client_label: str = "cli"
):
    """
    Base worker using geode query command.
    All client types use this same underlying mechanism.
    """
    queries = ";".join(["RETURN 1" for _ in range(batch_size)])

    while not stop_event.is_set():
        start = time.perf_counter()
        try:
            if use_docker:
                cmd = [
                    "docker", "compose", "exec", "-T", "geode",
                    "geode", "query", "--server", "localhost:3141", "--insecure",
                    queries
                ]
            else:
                cmd = [
                    "geode", "query", "--server", f"{host}:{port}", "--insecure",
                    queries
                ]

            result = subprocess.run(cmd, capture_output=True, timeout=30.0)
            latency = (time.perf_counter() - start) * 1000

            if result.returncode == 0:
                successful.add(batch_size)
            else:
                failed.add(batch_size)

            latencies.add(latency / batch_size)

        except Exception:
            failed.add(batch_size)


# =============================================================================
# Generic Client Benchmark Runner
# =============================================================================

def run_client_benchmark(
    client_name: str,
    workers: int,
    duration: int,
    batch_size: int,
    host: str,
    port: int,
    use_docker: bool
) -> ClientResult:
    """
    Run a benchmark for any client type.
    All clients use the same underlying subprocess mechanism.
    """
    stop_event = threading.Event()
    successful = AtomicCounter()
    failed = AtomicCounter()
    latencies = LatencyCollector()

    threads = []
    for i in range(workers):
        t = threading.Thread(
            target=base_worker,
            args=(i, stop_event, successful, failed, latencies, batch_size, host, port, use_docker, client_name),
            daemon=True
        )
        t.start()
        threads.append(t)

    start = time.monotonic()
    time.sleep(duration)
    stop_event.set()

    for t in threads:
        t.join(timeout=2.0)

    elapsed = time.monotonic() - start
    total_successful = successful.value
    throughput = total_successful / elapsed if elapsed > 0 else 0

    samples = latencies.samples
    if samples:
        sorted_samples = sorted(samples)
        p50 = sorted_samples[len(sorted_samples) // 2]
        p99_idx = min(int(len(sorted_samples) * 0.99), len(sorted_samples) - 1)
        p99 = sorted_samples[p99_idx]
    else:
        p50 = p99 = 0

    return ClientResult(
        client_name=client_name,
        workers=workers,
        total_queries=total_successful + failed.value,
        successful_queries=total_successful,
        failed_queries=failed.value,
        throughput_qps=throughput,
        latency_p50_ms=p50,
        latency_p99_ms=p99,
        duration_seconds=elapsed,
        status="OK"
    )


# =============================================================================
# Client-Specific Wrappers (for future native implementation)
# =============================================================================

def run_cli_benchmark(workers: int, duration: int, batch_size: int, host: str, port: int, use_docker: bool) -> ClientResult:
    """CLI client benchmark - uses geode CLI directly."""
    return run_client_benchmark("cli", workers, duration, batch_size, host, port, use_docker)


def run_go_benchmark(workers: int, duration: int, batch_size: int, host: str, port: int, use_docker: bool) -> Optional[ClientResult]:
    """
    Go client benchmark.

    Note: Currently uses subprocess. For native Go client benchmarks,
    use the geode-client-go repository directly.
    """
    # Check if Go is available (for future native implementation)
    if not shutil.which("go"):
        print("  Go not found, using subprocess fallback")

    return run_client_benchmark("go", workers, duration, batch_size, host, port, use_docker)


def run_python_benchmark(workers: int, duration: int, batch_size: int, host: str, port: int, use_docker: bool) -> Optional[ClientResult]:
    """
    Python client benchmark.

    Note: Currently uses subprocess. For native Python client benchmarks,
    use the geode-client-python repository directly.
    """
    return run_client_benchmark("python", workers, duration, batch_size, host, port, use_docker)


def run_rust_benchmark(workers: int, duration: int, batch_size: int, host: str, port: int, use_docker: bool) -> Optional[ClientResult]:
    """
    Rust client benchmark.

    Note: Currently uses subprocess. For native Rust client benchmarks,
    use the geode-client-rust repository directly.
    """
    # Check if Rust/Cargo is available (for future native implementation)
    if not shutil.which("cargo"):
        print("  Cargo not found, using subprocess fallback")

    return run_client_benchmark("rust", workers, duration, batch_size, host, port, use_docker)


def run_zig_benchmark(workers: int, duration: int, batch_size: int, host: str, port: int, use_docker: bool) -> Optional[ClientResult]:
    """
    Zig client benchmark.

    Note: Currently uses subprocess. For native Zig client benchmarks,
    use the geode-client-zig repository directly.
    """
    # Check if Zig is available (for future native implementation)
    if not shutil.which("zig"):
        print("  Zig not found, using subprocess fallback")

    return run_client_benchmark("zig", workers, duration, batch_size, host, port, use_docker)


def run_nodejs_benchmark(workers: int, duration: int, batch_size: int, host: str, port: int, use_docker: bool) -> Optional[ClientResult]:
    """
    Node.js client benchmark.

    Note: Currently uses subprocess. For native Node.js client benchmarks,
    use the geode-client-nodejs repository directly.
    """
    # Check if Node.js is available (for future native implementation)
    if not shutil.which("node"):
        print("  Node.js not found, using subprocess fallback")

    return run_client_benchmark("nodejs", workers, duration, batch_size, host, port, use_docker)


# =============================================================================
# Multi-Client Orchestrator
# =============================================================================

# Map client names to their benchmark functions
CLIENT_BENCHMARKS = {
    "cli": run_cli_benchmark,
    "go": run_go_benchmark,
    "python": run_python_benchmark,
    "rust": run_rust_benchmark,
    "zig": run_zig_benchmark,
    "nodejs": run_nodejs_benchmark,
    "node": run_nodejs_benchmark,  # Alias
}

ALL_CLIENTS = ["cli", "go", "python", "rust", "zig", "nodejs"]


def run_multi_client_benchmark(
    clients: List[str],
    workers_per_client: int,
    duration: int,
    batch_size: int,
    host: str,
    port: int,
    use_docker: bool,
    output_dir: Path
) -> MultiClientResult:
    """
    Run benchmarks with multiple clients in parallel.
    """
    print(f"\n{'='*70}")
    print("MULTI-CLIENT HIGH-THROUGHPUT BENCHMARK")
    print(f"{'='*70}")
    print(f"Clients: {', '.join(clients)}")
    print(f"Workers per client: {workers_per_client}")
    print(f"Duration: {duration}s")
    print(f"Batch size: {batch_size}")
    print(f"Host: {host}:{port}")
    print()

    output_dir.mkdir(parents=True, exist_ok=True)
    client_results = []
    futures = {}

    start_time = time.monotonic()

    with ThreadPoolExecutor(max_workers=len(clients)) as executor:
        for client in clients:
            if client not in CLIENT_BENCHMARKS:
                print(f"  Unknown client: {client}, skipping")
                continue

            benchmark_fn = CLIENT_BENCHMARKS[client]
            future = executor.submit(
                benchmark_fn,
                workers_per_client, duration, batch_size, host, port, use_docker
            )
            futures[future] = client
            print(f"  Started {client} benchmark with {workers_per_client} workers")

        # Collect results
        for future in as_completed(futures):
            client_name = futures[future]
            try:
                result = future.result()
                if result:
                    client_results.append(result)
                    print(f"  {client_name}: {result.successful_queries:,} queries, {result.throughput_qps:,.0f} qps")
            except Exception as e:
                print(f"  {client_name} failed: {e}")

    total_duration = time.monotonic() - start_time

    # Aggregate results
    aggregate_throughput = sum(r.throughput_qps for r in client_results)
    aggregate_successful = sum(r.successful_queries for r in client_results)
    aggregate_failed = sum(r.failed_queries for r in client_results)
    aggregate_total = aggregate_successful + aggregate_failed
    total_workers = len(client_results) * workers_per_client

    CLAIMED_MAX = 100_000
    achieved_pct = (aggregate_throughput / CLAIMED_MAX) * 100

    if aggregate_throughput >= CLAIMED_MAX:
        status = "VERIFIED"
    elif aggregate_throughput >= 10_000:
        status = "PARTIAL"
    elif aggregate_throughput >= 1_000:
        status = "BASELINE"
    else:
        status = "LIMITED"

    return MultiClientResult(
        benchmark_name="multi_client_high_throughput",
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        total_duration_seconds=total_duration,
        clients_used=[r.client_name for r in client_results],
        total_workers=total_workers,
        aggregate_throughput_qps=aggregate_throughput,
        aggregate_total_queries=aggregate_total,
        aggregate_successful_queries=aggregate_successful,
        aggregate_failed_queries=aggregate_failed,
        client_results=[asdict(r) for r in client_results],
        claimed_max_qps=CLAIMED_MAX,
        achieved_percentage=achieved_pct,
        status=status
    )


def print_result(result: MultiClientResult):
    """Print multi-client benchmark results."""
    print(f"\n{'='*70}")
    print("MULTI-CLIENT BENCHMARK RESULTS")
    print(f"{'='*70}")
    print(f"Timestamp: {result.timestamp}")
    print(f"Duration: {result.total_duration_seconds:.2f}s")
    print(f"Clients: {', '.join(result.clients_used)}")
    print(f"Total Workers: {result.total_workers}")
    print()
    print("PER-CLIENT RESULTS:")
    for cr in result.client_results:
        print(f"  {cr['client_name']:8} | {cr['successful_queries']:>10,} queries | {cr['throughput_qps']:>10,.0f} qps | p50={cr['latency_p50_ms']:.1f}ms p99={cr['latency_p99_ms']:.1f}ms")
    print()
    print("AGGREGATE:")
    print(f"  Total queries:    {result.aggregate_total_queries:,}")
    print(f"  Successful:       {result.aggregate_successful_queries:,}")
    print(f"  Failed:           {result.aggregate_failed_queries:,}")
    print(f"  Throughput:       {result.aggregate_throughput_qps:,.0f} qps")
    print()
    print("CLAIM VERIFICATION:")
    print(f"  Claimed max:      {result.claimed_max_qps:,} qps")
    print(f"  Achieved:         {result.achieved_percentage:.2f}%")
    print(f"  Status:           {result.status}")
    print(f"{'='*70}")


def main():
    parser = argparse.ArgumentParser(
        description="Multi-client high-throughput benchmark for Geode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available clients:
  cli     - Geode CLI (baseline)
  go      - Go client
  python  - Python client
  rust    - Rust client
  zig     - Zig client
  nodejs  - Node.js client
  all     - All available clients

Note: All clients currently use subprocess-based execution.
For native client benchmarks, use the actual client libraries
from their respective repositories.

Examples:
  # CLI only (baseline)
  python multi_client_benchmark.py --clients cli --workers 50

  # Multiple clients for aggregate throughput
  python multi_client_benchmark.py --clients cli,go,python --workers 100

  # All clients in parallel
  python multi_client_benchmark.py --clients all --workers 50 --duration 120
        """
    )
    parser.add_argument(
        "--clients", "-c",
        type=str,
        default="cli",
        help="Comma-separated list of clients or 'all' (default: cli)"
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=50,
        help="Workers per client (default: 50)"
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=60,
        help="Duration in seconds (default: 60)"
    )
    parser.add_argument(
        "--batch-size", "-b",
        type=int,
        default=10,
        help="Batch size for queries (default: 10)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Geode host (default: localhost)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=3141,
        help="Geode port (default: 3141)"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output JSON file path"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="reports/multi_client",
        help="Output directory for per-client results"
    )
    parser.add_argument(
        "--no-docker",
        action="store_true",
        help="Don't use docker compose for CLI client"
    )

    args = parser.parse_args()

    # Parse clients
    if args.clients == "all":
        clients = ALL_CLIENTS
    else:
        clients = [c.strip() for c in args.clients.split(",")]

    # Run benchmark
    result = run_multi_client_benchmark(
        clients=clients,
        workers_per_client=args.workers,
        duration=args.duration,
        batch_size=args.batch_size,
        host=args.host,
        port=args.port,
        use_docker=not args.no_docker,
        output_dir=Path(args.output_dir)
    )

    # Print results
    print_result(result)

    # Save to file
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(asdict(result), f, indent=2)
        print(f"\nResults saved to: {output_path}")

    sys.exit(0)


if __name__ == "__main__":
    main()
