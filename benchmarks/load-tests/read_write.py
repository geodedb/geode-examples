#!/usr/bin/env python3
"""
Read-Write Mixed Workload Benchmark

Verifies claim: Read-write throughput 10,000-50,000 txn/sec
Source: Overview, Performance
CANARY: REQ=REQ-PERF-READWRITE-001; FEATURE="ReadWriteThroughput"; ASPECT=Performance; STATUS=TESTED

This benchmark measures mixed read/write workload throughput to verify
Geode's claimed throughput for typical OLTP workloads.
"""
import argparse
import asyncio
import json
import random
import statistics
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List


@dataclass
class BenchmarkResult:
    """Result of a throughput benchmark run."""
    benchmark_name: str
    timestamp: str
    duration_seconds: float
    total_operations: int
    read_operations: int
    write_operations: int
    successful_operations: int
    failed_operations: int
    throughput_ops: float
    read_throughput_ops: float
    write_throughput_ops: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    latency_avg_ms: float
    read_latency_avg_ms: float
    write_latency_avg_ms: float
    concurrent_workers: int
    read_write_ratio: str
    claimed_min_ops: int
    claimed_max_ops: int
    achieved_percentage: float
    status: str


class GeodeShellClient:
    """Geode client using shell commands."""

    def __init__(self, host: str = "localhost", port: int = 3141, use_docker: bool = True, insecure: bool = True):
        self.host = host
        self.port = port
        self.use_docker = use_docker
        self.insecure = insecure

    def execute(self, query: str, timeout: float = 5.0) -> tuple[bool, float]:
        """Execute a query and return (success, latency_ms)."""
        start = time.perf_counter()
        try:
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
                    "--timeout", str(int(timeout)),
                ]
                if self.insecure:
                    cmd.append("--insecure")
                cmd.append(query)

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            latency = (time.perf_counter() - start) * 1000
            return result.returncode == 0, latency
        except Exception:
            latency = (time.perf_counter() - start) * 1000
            return False, latency


async def run_worker(
    worker_id: int,
    duration_seconds: float,
    read_ratio: float,
    results: List[dict],
    use_docker: bool
):
    """Worker that executes mixed read/write operations."""
    client = GeodeShellClient(use_docker=use_docker)
    start_time = time.monotonic()

    while time.monotonic() - start_time < duration_seconds:
        is_read = random.random() < read_ratio

        if is_read:
            query = "MATCH (n:BenchNode) RETURN n.value LIMIT 10"
            op_type = "read"
        else:
            node_id = f"bench_{worker_id}_{uuid.uuid4().hex[:8]}"
            query = f"CREATE (:BenchNode {{id: '{node_id}', value: {random.randint(1, 1000)}, ts: timestamp()}})"
            op_type = "write"

        success, latency = client.execute(query)
        results.append({
            "success": success,
            "latency": latency,
            "type": op_type
        })
        await asyncio.sleep(0)


async def run_benchmark(
    concurrent_workers: int = 10,
    duration_seconds: int = 30,
    read_ratio: float = 0.7,
    use_docker: bool = True
) -> BenchmarkResult:
    """Run the read-write mixed workload benchmark."""
    print(f"Starting read-write benchmark...")
    print(f"  Workers: {concurrent_workers}")
    print(f"  Duration: {duration_seconds}s")
    print(f"  Read ratio: {read_ratio:.0%}")

    # Setup: Create some initial nodes to read
    client = GeodeShellClient(use_docker=use_docker)
    print("  Creating seed data...")
    for i in range(100):
        client.execute(f"CREATE (:BenchNode {{id: 'seed_{i}', value: {i}}})")

    results: List[dict] = []

    tasks = [
        run_worker(i, duration_seconds, read_ratio, results, use_docker)
        for i in range(concurrent_workers)
    ]

    start_time = time.monotonic()
    await asyncio.gather(*tasks)
    actual_duration = time.monotonic() - start_time

    # Calculate metrics
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    reads = [r for r in successful if r["type"] == "read"]
    writes = [r for r in successful if r["type"] == "write"]

    all_latencies = [r["latency"] for r in successful] if successful else [0]
    read_latencies = [r["latency"] for r in reads] if reads else [0]
    write_latencies = [r["latency"] for r in writes] if writes else [0]

    throughput = len(successful) / actual_duration if actual_duration > 0 else 0
    read_throughput = len(reads) / actual_duration if actual_duration > 0 else 0
    write_throughput = len(writes) / actual_duration if actual_duration > 0 else 0

    sorted_latencies = sorted(all_latencies)
    p50 = sorted_latencies[int(len(sorted_latencies) * 0.50)] if sorted_latencies else 0
    p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)] if sorted_latencies else 0
    p99 = sorted_latencies[min(int(len(sorted_latencies) * 0.99), len(sorted_latencies) - 1)] if sorted_latencies else 0

    CLAIMED_MIN = 10_000
    CLAIMED_MAX = 50_000
    achieved_pct = (throughput / CLAIMED_MAX) * 100

    if throughput >= CLAIMED_MAX:
        status = "VERIFIED"
    elif throughput >= CLAIMED_MIN:
        status = "PARTIAL"
    else:
        status = "FAILED"

    # Cleanup
    client.execute("MATCH (n:BenchNode) DETACH DELETE n")

    return BenchmarkResult(
        benchmark_name="read_write_mixed",
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        duration_seconds=actual_duration,
        total_operations=len(results),
        read_operations=len(reads) + len([r for r in failed if r.get("type") == "read"]),
        write_operations=len(writes) + len([r for r in failed if r.get("type") == "write"]),
        successful_operations=len(successful),
        failed_operations=len(failed),
        throughput_ops=throughput,
        read_throughput_ops=read_throughput,
        write_throughput_ops=write_throughput,
        latency_p50_ms=p50,
        latency_p95_ms=p95,
        latency_p99_ms=p99,
        latency_avg_ms=statistics.mean(all_latencies) if all_latencies else 0,
        read_latency_avg_ms=statistics.mean(read_latencies) if read_latencies else 0,
        write_latency_avg_ms=statistics.mean(write_latencies) if write_latencies else 0,
        concurrent_workers=concurrent_workers,
        read_write_ratio=f"{int(read_ratio*100)}:{int((1-read_ratio)*100)}",
        claimed_min_ops=CLAIMED_MIN,
        claimed_max_ops=CLAIMED_MAX,
        achieved_percentage=achieved_pct,
        status=status
    )


def print_result(result: BenchmarkResult):
    """Print benchmark results."""
    print("\n" + "=" * 60)
    print("READ-WRITE MIXED WORKLOAD BENCHMARK RESULTS")
    print("=" * 60)
    print(f"Timestamp: {result.timestamp}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    print(f"Workers: {result.concurrent_workers}")
    print(f"Read/Write Ratio: {result.read_write_ratio}")
    print()
    print("THROUGHPUT:")
    print(f"  Total ops:        {result.total_operations:,}")
    print(f"  Successful:       {result.successful_operations:,}")
    print(f"  Failed:           {result.failed_operations:,}")
    print(f"  Combined:         {result.throughput_ops:,.0f} ops/sec")
    print(f"  Read:             {result.read_throughput_ops:,.0f} ops/sec")
    print(f"  Write:            {result.write_throughput_ops:,.0f} ops/sec")
    print()
    print("LATENCY (ms):")
    print(f"  P50:              {result.latency_p50_ms:.2f}")
    print(f"  P95:              {result.latency_p95_ms:.2f}")
    print(f"  P99:              {result.latency_p99_ms:.2f}")
    print(f"  Avg (all):        {result.latency_avg_ms:.2f}")
    print(f"  Avg (read):       {result.read_latency_avg_ms:.2f}")
    print(f"  Avg (write):      {result.write_latency_avg_ms:.2f}")
    print()
    print("CLAIM VERIFICATION:")
    print(f"  Claimed range:    {result.claimed_min_ops:,} - {result.claimed_max_ops:,} ops/sec")
    print(f"  Achieved:         {result.achieved_percentage:.1f}% of max")
    print(f"  Status:           {result.status}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Read-write mixed workload benchmark")
    parser.add_argument("--workers", "-w", type=int, default=10)
    parser.add_argument("--duration", "-d", type=int, default=30)
    parser.add_argument("--read-ratio", "-r", type=float, default=0.7, help="Ratio of reads (0.0-1.0)")
    parser.add_argument("--output", "-o", type=str)
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--no-docker", action="store_true")
    parser.add_argument("--target", type=int, default=50000)

    args = parser.parse_args()

    result = asyncio.run(run_benchmark(
        concurrent_workers=args.workers,
        duration_seconds=args.duration,
        read_ratio=args.read_ratio,
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
