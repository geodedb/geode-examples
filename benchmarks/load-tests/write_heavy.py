#!/usr/bin/env python3
"""
Write-Heavy Workload Benchmark

Verifies claim: Write-heavy throughput 5,000-20,000 txn/sec
Source: Overview, Performance
CANARY: REQ=REQ-PERF-WRITE-001; FEATURE="WriteThroughput"; ASPECT=Performance; STATUS=TESTED

This benchmark measures write-heavy workload throughput to verify
Geode's claimed throughput for write-intensive operations.
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
from datetime import datetime
from pathlib import Path
from typing import List


@dataclass
class BenchmarkResult:
    """Result of a write-heavy benchmark run."""
    benchmark_name: str
    timestamp: str
    duration_seconds: float
    total_writes: int
    successful_writes: int
    failed_writes: int
    throughput_wps: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    latency_avg_ms: float
    latency_min_ms: float
    latency_max_ms: float
    concurrent_workers: int
    nodes_created: int
    relationships_created: int
    claimed_min_wps: int
    claimed_max_wps: int
    achieved_percentage: float
    status: str


class GeodeShellClient:
    """Geode client using shell commands."""

    def __init__(self, use_docker: bool = True):
        self.use_docker = use_docker

    def execute(self, query: str, timeout: float = 10.0) -> tuple[bool, float]:
        """Execute a query and return (success, latency_ms)."""
        start = time.perf_counter()
        try:
            if self.use_docker:
                cmd = ["docker", "compose", "exec", "-T", "geode", "geode", "shell", "-c", query]
            else:
                cmd = ["geode", "shell", "-c", query]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            latency = (time.perf_counter() - start) * 1000
            return result.returncode == 0, latency
        except Exception:
            latency = (time.perf_counter() - start) * 1000
            return False, latency


async def run_worker(
    worker_id: int,
    duration_seconds: float,
    results: List[dict],
    use_docker: bool
):
    """Worker that executes write-heavy operations."""
    client = GeodeShellClient(use_docker=use_docker)
    start_time = time.monotonic()
    node_counter = 0

    while time.monotonic() - start_time < duration_seconds:
        op_type = random.choice(["create_node", "create_node", "create_relationship", "update", "delete"])
        node_id = f"w{worker_id}_n{node_counter}"

        if op_type == "create_node":
            query = f"""CREATE (:WriteTest {{
                id: '{node_id}',
                worker: {worker_id},
                value: {random.randint(1, 10000)},
                data: '{uuid.uuid4().hex}',
                ts: timestamp()
            }})"""
            node_counter += 1
        elif op_type == "create_relationship":
            # Create a node and relationship together
            target_id = f"w{worker_id}_n{max(0, node_counter - random.randint(1, 5))}"
            query = f"""
                MATCH (a:WriteTest {{id: '{target_id}'}})
                CREATE (b:WriteTest {{id: '{node_id}', worker: {worker_id}, value: {random.randint(1, 10000)}}})
                CREATE (a)-[:CONNECTS {{weight: {random.random():.4f}}}]->(b)
            """
            node_counter += 1
        elif op_type == "update":
            target_id = f"w{worker_id}_n{max(0, node_counter - random.randint(1, 10))}"
            query = f"""
                MATCH (n:WriteTest {{id: '{target_id}'}})
                SET n.value = {random.randint(1, 10000)}, n.updated = timestamp()
            """
        else:  # delete
            if node_counter > 10:
                target_id = f"w{worker_id}_n{random.randint(0, node_counter - 10)}"
                query = f"MATCH (n:WriteTest {{id: '{target_id}'}}) DETACH DELETE n"
            else:
                continue

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
    use_docker: bool = True
) -> BenchmarkResult:
    """Run the write-heavy workload benchmark."""
    print(f"Starting write-heavy benchmark...")
    print(f"  Workers: {concurrent_workers}")
    print(f"  Duration: {duration_seconds}s")

    results: List[dict] = []

    tasks = [
        run_worker(i, duration_seconds, results, use_docker)
        for i in range(concurrent_workers)
    ]

    start_time = time.monotonic()
    await asyncio.gather(*tasks)
    actual_duration = time.monotonic() - start_time

    # Calculate metrics
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    latencies = [r["latency"] for r in successful] if successful else [0]

    nodes_created = len([r for r in successful if r["type"] in ["create_node", "create_relationship"]])
    rels_created = len([r for r in successful if r["type"] == "create_relationship"])

    throughput = len(successful) / actual_duration if actual_duration > 0 else 0

    sorted_latencies = sorted(latencies)
    p50 = sorted_latencies[int(len(sorted_latencies) * 0.50)] if sorted_latencies else 0
    p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)] if sorted_latencies else 0
    p99 = sorted_latencies[min(int(len(sorted_latencies) * 0.99), len(sorted_latencies) - 1)] if sorted_latencies else 0

    CLAIMED_MIN = 5_000
    CLAIMED_MAX = 20_000
    achieved_pct = (throughput / CLAIMED_MAX) * 100

    if throughput >= CLAIMED_MAX:
        status = "VERIFIED"
    elif throughput >= CLAIMED_MIN:
        status = "PARTIAL"
    else:
        status = "FAILED"

    # Cleanup
    client = GeodeShellClient(use_docker=use_docker)
    client.execute("MATCH (n:WriteTest) DETACH DELETE n")

    return BenchmarkResult(
        benchmark_name="write_heavy",
        timestamp=datetime.utcnow().isoformat() + "Z",
        duration_seconds=actual_duration,
        total_writes=len(results),
        successful_writes=len(successful),
        failed_writes=len(failed),
        throughput_wps=throughput,
        latency_p50_ms=p50,
        latency_p95_ms=p95,
        latency_p99_ms=p99,
        latency_avg_ms=statistics.mean(latencies) if latencies else 0,
        latency_min_ms=min(latencies) if latencies else 0,
        latency_max_ms=max(latencies) if latencies else 0,
        concurrent_workers=concurrent_workers,
        nodes_created=nodes_created,
        relationships_created=rels_created,
        claimed_min_wps=CLAIMED_MIN,
        claimed_max_wps=CLAIMED_MAX,
        achieved_percentage=achieved_pct,
        status=status
    )


def print_result(result: BenchmarkResult):
    """Print benchmark results."""
    print("\n" + "=" * 60)
    print("WRITE-HEAVY WORKLOAD BENCHMARK RESULTS")
    print("=" * 60)
    print(f"Timestamp: {result.timestamp}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    print(f"Workers: {result.concurrent_workers}")
    print()
    print("THROUGHPUT:")
    print(f"  Total writes:     {result.total_writes:,}")
    print(f"  Successful:       {result.successful_writes:,}")
    print(f"  Failed:           {result.failed_writes:,}")
    print(f"  Throughput:       {result.throughput_wps:,.0f} writes/sec")
    print(f"  Nodes created:    {result.nodes_created:,}")
    print(f"  Rels created:     {result.relationships_created:,}")
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
    print(f"  Claimed range:    {result.claimed_min_wps:,} - {result.claimed_max_wps:,} writes/sec")
    print(f"  Achieved:         {result.achieved_percentage:.1f}% of max")
    print(f"  Status:           {result.status}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Write-heavy workload benchmark")
    parser.add_argument("--workers", "-w", type=int, default=10)
    parser.add_argument("--duration", "-d", type=int, default=30)
    parser.add_argument("--output", "-o", type=str)
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--no-docker", action="store_true")
    parser.add_argument("--target", type=int, default=20000)

    args = parser.parse_args()

    result = asyncio.run(run_benchmark(
        concurrent_workers=args.workers,
        duration_seconds=args.duration,
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
