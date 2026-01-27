#!/usr/bin/env python3
"""
Native Client High-Throughput Benchmark for Geode

This benchmark uses ACTUAL native client libraries with persistent QUIC connections
for realistic high-throughput testing. Unlike the multi_client_benchmark.py which
spawns subprocesses, this uses real async connections.

CANARY: REQ=REQ-PERF-NATIVE-BENCH-001; FEATURE="NativeClientBench"; ASPECT=Performance; STATUS=TESTED

Requirements:
    pip install aioquic  # For Python QUIC client

Usage:
    python benchmarks/load-tests/native_client_benchmark.py --host localhost --port 3142
"""
import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# Add geode-client-python to path
CLIENT_PATH = Path(__file__).parent.parent.parent.parent / "geode-client-python"
sys.path.insert(0, str(CLIENT_PATH))

try:
    from geode_client import Client, Connection
    NATIVE_CLIENT_AVAILABLE = True
except ImportError:
    NATIVE_CLIENT_AVAILABLE = False
    print("Warning: geode_client not available. Install from geode-client-python.")


@dataclass
class BenchmarkResult:
    """Result from benchmark run."""
    timestamp: str
    duration_seconds: float
    total_queries: int
    successful_queries: int
    failed_queries: int
    throughput_qps: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    latency_avg_ms: float
    workers: int
    queries_per_worker: int
    status: str


async def benchmark_worker(
    conn: "Connection",
    num_queries: int,
    latencies: List[float],
    errors: List[str],
):
    """Single worker that runs queries on a persistent connection."""
    for _ in range(num_queries):
        start = time.perf_counter()
        try:
            result, _ = await conn.query("RETURN 1")
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)
        except Exception as e:
            errors.append(str(e))


async def run_benchmark(
    host: str,
    port: int,
    workers: int,
    queries_per_worker: int,
    insecure: bool = True,
    quiet: bool = False,
) -> BenchmarkResult:
    """Run the benchmark with multiple concurrent workers."""
    if not quiet:
        print(f"\nConnecting to {host}:{port}...")

    # Create client factory
    client = Client(host=host, port=port, skip_verify=insecure)

    # Create multiple connections (one per worker)
    connections = []
    for i in range(workers):
        try:
            conn = await client.connect()
            connections.append(conn)
        except Exception as e:
            if not quiet:
                print(f"  Worker {i} connection failed: {e}")

    if not connections:
        return BenchmarkResult(
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration_seconds=0,
            total_queries=0,
            successful_queries=0,
            failed_queries=workers * queries_per_worker,
            throughput_qps=0,
            latency_p50_ms=0,
            latency_p95_ms=0,
            latency_p99_ms=0,
            latency_avg_ms=0,
            workers=workers,
            queries_per_worker=queries_per_worker,
            status="FAILED",
        )

    if not quiet:
        print(f"  Connected {len(connections)} workers")

    # Collect latencies and errors
    all_latencies: List[List[float]] = [[] for _ in connections]
    all_errors: List[List[str]] = [[] for _ in connections]

    if not quiet:
        print(f"Running {queries_per_worker} queries per worker...")
    start_time = time.perf_counter()

    # Run all workers concurrently
    tasks = [
        benchmark_worker(conn, queries_per_worker, all_latencies[i], all_errors[i])
        for i, conn in enumerate(connections)
    ]
    await asyncio.gather(*tasks, return_exceptions=True)

    duration = time.perf_counter() - start_time

    # Close connections
    for conn in connections:
        try:
            await conn.close()
        except:
            pass

    # Aggregate results
    latencies = [l for worker_latencies in all_latencies for l in worker_latencies]
    errors = [e for worker_errors in all_errors for e in worker_errors]

    successful = len(latencies)
    failed = len(errors)
    total = successful + failed

    if latencies:
        sorted_latencies = sorted(latencies)
        p50 = sorted_latencies[len(sorted_latencies) // 2]
        p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]
        p99 = sorted_latencies[int(len(sorted_latencies) * 0.99)]
        avg = statistics.mean(latencies)
    else:
        p50 = p95 = p99 = avg = 0

    throughput = successful / duration if duration > 0 else 0

    # Determine status
    if throughput >= 10000:
        status = "EXCELLENT"
    elif throughput >= 1000:
        status = "GOOD"
    elif throughput >= 100:
        status = "ACCEPTABLE"
    else:
        status = "LIMITED"

    return BenchmarkResult(
        timestamp=datetime.now(timezone.utc).isoformat(),
        duration_seconds=duration,
        total_queries=total,
        successful_queries=successful,
        failed_queries=failed,
        throughput_qps=throughput,
        latency_p50_ms=p50,
        latency_p95_ms=p95,
        latency_p99_ms=p99,
        latency_avg_ms=avg,
        workers=len(connections),
        queries_per_worker=queries_per_worker,
        status=status,
    )


def print_result(result: BenchmarkResult):
    """Print benchmark results."""
    print(f"\n{'='*70}")
    print("NATIVE CLIENT BENCHMARK RESULTS")
    print(f"{'='*70}")
    print(f"Timestamp: {result.timestamp}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    print(f"Workers: {result.workers}")
    print(f"Queries/worker: {result.queries_per_worker}")
    print()
    print("RESULTS:")
    print(f"  Total queries:    {result.total_queries:,}")
    print(f"  Successful:       {result.successful_queries:,}")
    print(f"  Failed:           {result.failed_queries:,}")
    print(f"  Throughput:       {result.throughput_qps:,.0f} qps")
    print()
    print("LATENCY:")
    print(f"  p50:  {result.latency_p50_ms:.2f}ms")
    print(f"  p95:  {result.latency_p95_ms:.2f}ms")
    print(f"  p99:  {result.latency_p99_ms:.2f}ms")
    print(f"  avg:  {result.latency_avg_ms:.2f}ms")
    print()
    print(f"STATUS: {result.status}")
    print(f"{'='*70}")


async def main():
    parser = argparse.ArgumentParser(description="Native client benchmark for Geode")
    parser.add_argument("--host", default="localhost", help="Server host")
    parser.add_argument("--port", type=int, default=3141, help="Server port")
    parser.add_argument("--workers", "-w", type=int, default=10, help="Number of concurrent workers")
    parser.add_argument("--queries", "-q", type=int, default=1000, help="Queries per worker")
    parser.add_argument("--insecure", action="store_true", default=True, help="Skip TLS verification")
    parser.add_argument("--output", "-o", type=str, help="Output JSON file")
    parser.add_argument("--json", action="store_true", help="Output results as JSON to stdout")

    args = parser.parse_args()

    if not NATIVE_CLIENT_AVAILABLE:
        if args.json:
            print(json.dumps({"error": "Native client not available", "status": "FAILED"}))
        else:
            print("ERROR: Native client not available.")
            print("Install with: cd ../geode-client-python && pip install -e .")
        sys.exit(1)

    if not args.json:
        print(f"\n{'='*70}")
        print("NATIVE CLIENT HIGH-THROUGHPUT BENCHMARK")
        print(f"{'='*70}")
        print(f"Host: {args.host}:{args.port}")
        print(f"Workers: {args.workers}")
        print(f"Queries per worker: {args.queries}")
        print(f"Total queries: {args.workers * args.queries:,}")

    result = await run_benchmark(
        host=args.host,
        port=args.port,
        workers=args.workers,
        queries_per_worker=args.queries,
        insecure=args.insecure,
        quiet=args.json,
    )

    if args.json:
        print(json.dumps(asdict(result)))
    else:
        print_result(result)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(asdict(result), f, indent=2)
        if not args.json:
            print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
