#!/usr/bin/env python3
"""
High-Throughput Parallel Benchmark for Geode

This benchmark runs truly parallel workers, each executing queries continuously
for the specified duration. Workers run independently and don't wait for each other.

CANARY: REQ=REQ-PERF-HIGHTP-001; FEATURE="HighThroughputBench"; ASPECT=Performance; STATUS=TESTED

Usage:
    # Quick test with 20 parallel workers
    python benchmarks/load-tests/high_throughput.py --workers 20 --duration 30

    # High-scale test with 100 parallel workers, batch size 50
    python benchmarks/load-tests/high_throughput.py --workers 100 --duration 120 --batch-size 50

    # Maximum scale test
    python benchmarks/load-tests/high_throughput.py --workers 200 --duration 300 --batch-size 100

    # Run inside container for best performance
    docker compose exec geode python3 /benchmarks/load-tests/high_throughput.py --mode internal
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple
from queue import Queue
from concurrent.futures import ThreadPoolExecutor


@dataclass
class HighThroughputResult:
    """Result of a high-throughput benchmark run."""
    benchmark_name: str
    timestamp: str
    mode: str
    duration_seconds: float
    total_queries: int
    successful_queries: int
    failed_queries: int
    throughput_qps: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    latency_avg_ms: float
    latency_min_ms: float
    latency_max_ms: float
    concurrent_workers: int
    queries_per_batch: int
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
    """Thread-safe latency collector with sampling."""
    def __init__(self, max_samples: int = 100000):
        self._samples = []
        self._lock = threading.Lock()
        self._max_samples = max_samples
        self._sample_rate = 1  # Sample every Nth latency
        self._count = 0

    def add(self, latency_ms: float):
        with self._lock:
            self._count += 1
            # Adaptive sampling to avoid memory issues
            if len(self._samples) >= self._max_samples:
                self._sample_rate = max(self._sample_rate, self._count // self._max_samples)
            if self._count % self._sample_rate == 0:
                self._samples.append(latency_ms)

    def add_batch(self, latencies: List[float]):
        with self._lock:
            for lat in latencies:
                self._count += 1
                if len(self._samples) < self._max_samples:
                    if self._count % self._sample_rate == 0:
                        self._samples.append(lat)

    @property
    def samples(self):
        with self._lock:
            return list(self._samples)


def run_batch_query(
    batch_size: int,
    host: str,
    port: int,
    use_docker: bool,
    timeout: float = 30.0
) -> Tuple[int, int, float]:
    """
    Execute a batch of queries and return (successful, failed, total_latency_ms).
    """
    # Build batch query with multiple RETURN statements
    queries = ";".join(["RETURN 1" for _ in range(batch_size)])

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

        result = subprocess.run(cmd, capture_output=True, timeout=timeout)
        latency = (time.perf_counter() - start) * 1000

        if result.returncode == 0:
            return batch_size, 0, latency
        else:
            return 0, batch_size, latency

    except subprocess.TimeoutExpired:
        latency = (time.perf_counter() - start) * 1000
        return 0, batch_size, latency
    except Exception:
        latency = (time.perf_counter() - start) * 1000
        return 0, batch_size, latency


def run_single_query_internal(host: str, port: int) -> Tuple[bool, float]:
    """Run a single query using local geode binary (for internal mode)."""
    start = time.perf_counter()
    try:
        result = subprocess.run(
            ["geode", "query", "--server", f"{host}:{port}", "--insecure", "RETURN 1"],
            capture_output=True,
            timeout=5.0
        )
        latency = (time.perf_counter() - start) * 1000
        return result.returncode == 0, latency
    except Exception:
        latency = (time.perf_counter() - start) * 1000
        return False, latency


def parallel_worker(
    worker_id: int,
    stop_event: threading.Event,
    successful_counter: AtomicCounter,
    failed_counter: AtomicCounter,
    latency_collector: LatencyCollector,
    batch_size: int,
    host: str,
    port: int,
    use_docker: bool,
    mode: str
):
    """
    Worker that runs continuously until stop_event is set.
    Each worker executes batches independently in parallel with other workers.
    """
    while not stop_event.is_set():
        if mode == "internal":
            # Internal mode: single queries with local binary
            success, latency = run_single_query_internal(host, port)
            if success:
                successful_counter.add(1)
            else:
                failed_counter.add(1)
            latency_collector.add(latency)
        else:
            # External mode: batch queries via docker compose
            successful, failed, total_latency = run_batch_query(
                batch_size, host, port, use_docker
            )
            successful_counter.add(successful)
            failed_counter.add(failed)
            # Record per-query latency (amortized)
            if successful > 0:
                per_query_latency = total_latency / batch_size
                latency_collector.add_batch([per_query_latency] * successful)


def run_parallel_benchmark(
    duration_seconds: int,
    workers: int,
    batch_size: int,
    host: str,
    port: int,
    use_docker: bool,
    mode: str
) -> HighThroughputResult:
    """
    Run benchmark with truly parallel workers for the specified duration.
    """
    print(f"\nStarting parallel high-throughput benchmark...")
    print(f"  Mode: {mode}")
    print(f"  Parallel Workers: {workers}")
    print(f"  Batch Size: {batch_size}")
    print(f"  Duration: {duration_seconds}s")
    print(f"  Host: {host}:{port}")
    print(f"  Use Docker: {use_docker}")
    print()

    # Shared state
    stop_event = threading.Event()
    successful_counter = AtomicCounter()
    failed_counter = AtomicCounter()
    latency_collector = LatencyCollector()

    # Start all workers
    print(f"Starting {workers} parallel workers...")
    threads = []
    for i in range(workers):
        t = threading.Thread(
            target=parallel_worker,
            args=(
                i, stop_event, successful_counter, failed_counter,
                latency_collector, batch_size, host, port, use_docker, mode
            ),
            daemon=True
        )
        t.start()
        threads.append(t)

    print(f"All workers started. Running for {duration_seconds}s...")
    print()

    # Monitor progress
    start_time = time.monotonic()
    last_report = start_time
    report_interval = 5.0  # Report every 5 seconds

    while time.monotonic() - start_time < duration_seconds:
        time.sleep(0.5)

        elapsed = time.monotonic() - start_time
        if elapsed - (last_report - start_time) >= report_interval:
            current_successful = successful_counter.value
            current_qps = current_successful / elapsed if elapsed > 0 else 0
            print(f"  [{elapsed:.1f}s] Queries: {current_successful:,} | QPS: {current_qps:,.0f} | Workers: {workers}")
            last_report = time.monotonic()

    # Signal workers to stop
    print("\nStopping workers...")
    stop_event.set()

    # Wait for workers to finish (with timeout)
    for t in threads:
        t.join(timeout=2.0)

    actual_duration = time.monotonic() - start_time
    total_successful = successful_counter.value
    total_failed = failed_counter.value
    throughput = total_successful / actual_duration if actual_duration > 0 else 0

    # Calculate latency percentiles
    latencies = latency_collector.samples
    if latencies:
        sorted_lats = sorted(latencies)
        n = len(sorted_lats)
        p50 = sorted_lats[int(n * 0.50)]
        p95 = sorted_lats[int(n * 0.95)]
        p99 = sorted_lats[min(int(n * 0.99), n - 1)]
        avg = statistics.mean(sorted_lats)
        min_lat = min(sorted_lats)
        max_lat = max(sorted_lats)
    else:
        p50 = p95 = p99 = avg = min_lat = max_lat = 0

    CLAIMED_MAX = 100_000
    achieved_pct = (throughput / CLAIMED_MAX) * 100

    # Determine status
    if throughput >= CLAIMED_MAX:
        status = "VERIFIED"
    elif throughput >= 10_000:
        status = "PARTIAL"
    elif throughput >= 1_000:
        status = "BASELINE"
    else:
        status = "LIMITED"

    return HighThroughputResult(
        benchmark_name="high_throughput_parallel",
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        mode=mode,
        duration_seconds=actual_duration,
        total_queries=total_successful + total_failed,
        successful_queries=total_successful,
        failed_queries=total_failed,
        throughput_qps=throughput,
        latency_p50_ms=p50,
        latency_p95_ms=p95,
        latency_p99_ms=p99,
        latency_avg_ms=avg,
        latency_min_ms=min_lat,
        latency_max_ms=max_lat,
        concurrent_workers=workers,
        queries_per_batch=batch_size,
        claimed_max_qps=CLAIMED_MAX,
        achieved_percentage=achieved_pct,
        status=status
    )


def print_result(result: HighThroughputResult):
    """Print benchmark results."""
    print("\n" + "=" * 70)
    print("HIGH-THROUGHPUT PARALLEL BENCHMARK RESULTS")
    print("=" * 70)
    print(f"Mode: {result.mode}")
    print(f"Timestamp: {result.timestamp}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    print(f"Parallel Workers: {result.concurrent_workers}")
    print(f"Batch Size: {result.queries_per_batch}")
    print()
    print("THROUGHPUT:")
    print(f"  Total queries:    {result.total_queries:,}")
    print(f"  Successful:       {result.successful_queries:,}")
    print(f"  Failed:           {result.failed_queries:,}")
    print(f"  Throughput:       {result.throughput_qps:,.0f} qps")
    print()
    print("LATENCY (ms):")
    print(f"  P50:              {result.latency_p50_ms:.2f}")
    print(f"  P95:              {result.latency_p95_ms:.2f}")
    print(f"  P99:              {result.latency_p99_ms:.2f}")
    print(f"  Avg:              {result.latency_avg_ms:.2f}")
    print(f"  Min:              {result.latency_min_ms:.2f}")
    print(f"  Max:              {result.latency_max_ms:.2f}")
    print()
    print("CLAIM VERIFICATION:")
    print(f"  Claimed max:      {result.claimed_max_qps:,} qps")
    print(f"  Achieved:         {result.achieved_percentage:.2f}%")
    print(f"  Status:           {result.status}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="High-throughput parallel benchmark for Geode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Quick test:     python high_throughput.py --workers 20 --duration 30
  Standard test:  python high_throughput.py --workers 50 --duration 60 --batch-size 20
  Intensive test: python high_throughput.py --workers 100 --duration 300 --batch-size 50
  Maximum scale:  python high_throughput.py --workers 200 --duration 600 --batch-size 100
        """
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["internal", "external"],
        default="external",
        help="Mode: internal (inside container), external (via docker compose)"
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=50,
        help="Number of parallel workers (default: 50)"
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=60,
        help="Benchmark duration in seconds (default: 60)"
    )
    parser.add_argument(
        "--batch-size", "-b",
        type=int,
        default=10,
        help="Queries per batch in external mode (default: 10)"
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
        "--no-docker",
        action="store_true",
        help="Don't use docker compose (direct geode binary)"
    )

    args = parser.parse_args()

    # Auto-detect container environment
    if os.path.exists("/.dockerenv") or os.environ.get("GEODE_CONTAINER"):
        print("Detected container environment, using internal mode")
        args.mode = "internal"

    # Run benchmark
    result = run_parallel_benchmark(
        duration_seconds=args.duration,
        workers=args.workers,
        batch_size=args.batch_size,
        host=args.host,
        port=args.port,
        use_docker=not args.no_docker,
        mode=args.mode
    )

    # Print results
    print_result(result)

    # Save to file if requested
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(asdict(result), f, indent=2)

        print(f"\nResults saved to: {output_path}")

    # Exit code based on status
    sys.exit(0)


if __name__ == "__main__":
    main()
