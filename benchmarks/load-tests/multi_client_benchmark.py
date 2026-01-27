#!/usr/bin/env python3
"""
Multi-Client High-Throughput Benchmark for Geode

This benchmark runs multiple NATIVE client implementations in parallel to achieve
maximum throughput. Each client type uses its respective native QUIC client library
with persistent connections for true high-throughput testing.

Supported Native Clients:
  - Go: geode-client-go (database/sql driver with QUIC)
  - Python: geode-client-python (async aioquic)
  - Rust: geode-client-rust (tokio + quinn)
  - Node.js: geode-client-nodejs (TypeScript QUIC)
  - Zig: geode-client-zig (native QUIC)

CANARY: REQ=REQ-PERF-MULTICLIENT-002; FEATURE="NativeMultiClientBench"; ASPECT=Performance; STATUS=TESTED

Usage:
    # Run with all available native clients
    python multi_client_benchmark.py --clients all --workers 10 --queries 1000

    # Run with specific clients
    python multi_client_benchmark.py --clients go,python,rust --workers 10 --queries 1000

    # High-scale test
    python multi_client_benchmark.py --clients all --workers 100 --queries 10000
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed


# Repository root (parent of geode-examples)
REPO_ROOT = Path(__file__).parent.parent.parent.parent


@dataclass
class ClientResult:
    """Result from a single client benchmark."""
    client_name: str
    workers: int
    queries_per_worker: int
    total_queries: int
    successful_queries: int
    failed_queries: int
    throughput_qps: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    latency_avg_ms: float
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


# =============================================================================
# Native Client Benchmark Runners
# =============================================================================

def check_go_available() -> Tuple[bool, str]:
    """Check if Go client benchmark is available."""
    go_benchmark = REPO_ROOT / "geode-client-go" / "cmd" / "benchmark" / "main.go"
    if not go_benchmark.exists():
        return False, f"Go benchmark not found at {go_benchmark}"
    if not shutil.which("go"):
        return False, "Go compiler not found in PATH"
    return True, str(go_benchmark.parent)


def check_rust_available() -> Tuple[bool, str]:
    """Check if Rust client benchmark is available."""
    rust_benchmark = REPO_ROOT / "geode-client-rust" / "examples" / "benchmark.rs"
    if not rust_benchmark.exists():
        return False, f"Rust benchmark not found at {rust_benchmark}"
    if not shutil.which("cargo"):
        return False, "Cargo not found in PATH"
    return True, str(REPO_ROOT / "geode-client-rust")


def check_nodejs_available() -> Tuple[bool, str]:
    """Check if Node.js client benchmark is available."""
    nodejs_benchmark = REPO_ROOT / "geode-client-nodejs" / "benchmarks" / "benchmark.ts"
    if not nodejs_benchmark.exists():
        return False, f"Node.js benchmark not found at {nodejs_benchmark}"
    if not shutil.which("npx"):
        return False, "npx not found in PATH"
    return True, str(REPO_ROOT / "geode-client-nodejs")


def check_python_available() -> Tuple[bool, str]:
    """Check if Python native client benchmark is available."""
    python_benchmark = REPO_ROOT / "geode-client-python" / "benchmarks" / "benchmark.py"
    python_venv = REPO_ROOT / "geode-client-python" / ".venv" / "bin" / "python"
    if not python_benchmark.exists():
        return False, f"Python benchmark not found at {python_benchmark}"
    if not python_venv.exists():
        return False, f"Python venv not found at {python_venv}"
    return True, str(REPO_ROOT / "geode-client-python")


def check_zig_available() -> Tuple[bool, str]:
    """Check if Zig client benchmark is available."""
    zig_benchmark = REPO_ROOT / "geode-client-zig" / "benchmark.zig"
    if not zig_benchmark.exists():
        return False, f"Zig benchmark not found at {zig_benchmark}"
    if not shutil.which("zig"):
        return False, "Zig compiler not found in PATH"
    return True, str(REPO_ROOT / "geode-client-zig")


def run_go_benchmark(host: str, port: int, workers: int, queries: int) -> Optional[ClientResult]:
    """Run Go native client benchmark."""
    available, path = check_go_available()
    if not available:
        print(f"  Go client: {path}")
        return None

    cmd = [
        "go", "run", "./cmd/benchmark",
        "--host", host,
        "--port", str(port),
        "--workers", str(workers),
        "--queries", str(queries),
        "--json"
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT / "geode-client-go"),
            capture_output=True,
            text=True,
            timeout=600
        )

        if result.returncode != 0:
            print(f"  Go benchmark failed: {result.stderr}")
            return None

        data = json.loads(result.stdout.strip())
        return ClientResult(
            client_name="go",
            workers=data.get("workers", workers),
            queries_per_worker=data.get("queries_per_worker", queries),
            total_queries=data.get("total_queries", 0),
            successful_queries=data.get("successful_queries", 0),
            failed_queries=data.get("failed_queries", 0),
            throughput_qps=data.get("throughput_qps", 0),
            latency_p50_ms=data.get("latency_p50_ms", 0),
            latency_p95_ms=data.get("latency_p95_ms", 0),
            latency_p99_ms=data.get("latency_p99_ms", 0),
            latency_avg_ms=data.get("latency_avg_ms", 0),
            duration_seconds=data.get("duration_seconds", 0),
            status=data.get("status", "UNKNOWN")
        )
    except subprocess.TimeoutExpired:
        print("  Go benchmark timed out")
        return None
    except json.JSONDecodeError as e:
        print(f"  Go benchmark JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"  Go benchmark error: {e}")
        return None


def run_rust_benchmark(host: str, port: int, workers: int, queries: int) -> Optional[ClientResult]:
    """Run Rust native client benchmark."""
    available, path = check_rust_available()
    if not available:
        print(f"  Rust client: {path}")
        return None

    cmd = [
        "cargo", "run", "--release", "--example", "benchmark", "--",
        "--host", host,
        "--port", str(port),
        "--workers", str(workers),
        "--queries", str(queries),
        "--json"
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT / "geode-client-rust"),
            capture_output=True,
            text=True,
            timeout=600
        )

        # Show any errors from stderr (excluding cargo build output)
        if result.stderr:
            # Filter out cargo build lines, show actual errors
            error_lines = [l for l in result.stderr.split('\n')
                          if l.strip() and not l.strip().startswith(('Compiling', 'Finished', 'Running', 'Downloaded', 'Downloading'))]
            if error_lines:
                print(f"  Rust stderr: {'; '.join(error_lines[:3])}")

        if result.returncode != 0:
            print(f"  Rust benchmark failed (exit code {result.returncode})")
            return None

        if not result.stdout.strip():
            print("  Rust benchmark produced no output")
            return None

        # Rust cargo outputs build info to stderr, JSON to stdout
        data = json.loads(result.stdout.strip())
        return ClientResult(
            client_name="rust",
            workers=data.get("workers", workers),
            queries_per_worker=data.get("queries_per_worker", queries),
            total_queries=data.get("total_queries", 0),
            successful_queries=data.get("successful_queries", 0),
            failed_queries=data.get("failed_queries", 0),
            throughput_qps=data.get("throughput_qps", 0),
            latency_p50_ms=data.get("latency_p50_ms", 0),
            latency_p95_ms=data.get("latency_p95_ms", 0),
            latency_p99_ms=data.get("latency_p99_ms", 0),
            latency_avg_ms=data.get("latency_avg_ms", 0),
            duration_seconds=data.get("duration_seconds", 0),
            status=data.get("status", "UNKNOWN")
        )
    except subprocess.TimeoutExpired:
        print("  Rust benchmark timed out")
        return None
    except json.JSONDecodeError as e:
        print(f"  Rust benchmark JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"  Rust benchmark error: {e}")
        return None


def run_nodejs_benchmark(host: str, port: int, workers: int, queries: int) -> Optional[ClientResult]:
    """Run Node.js native client benchmark."""
    available, path = check_nodejs_available()
    if not available:
        print(f"  Node.js client: {path}")
        return None

    cmd = [
        "npx", "tsx", "benchmarks/benchmark.ts",
        "--host", host,
        "--port", str(port),
        "--workers", str(workers),
        "--queries", str(queries),
        "--json"
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT / "geode-client-nodejs"),
            capture_output=True,
            text=True,
            timeout=600
        )

        if result.returncode != 0:
            print(f"  Node.js benchmark failed: {result.stderr}")
            return None

        data = json.loads(result.stdout.strip())
        return ClientResult(
            client_name="nodejs",
            workers=data.get("workers", workers),
            queries_per_worker=data.get("queries_per_worker", queries),
            total_queries=data.get("total_queries", 0),
            successful_queries=data.get("successful_queries", 0),
            failed_queries=data.get("failed_queries", 0),
            throughput_qps=data.get("throughput_qps", 0),
            latency_p50_ms=data.get("latency_p50_ms", 0),
            latency_p95_ms=data.get("latency_p95_ms", 0),
            latency_p99_ms=data.get("latency_p99_ms", 0),
            latency_avg_ms=data.get("latency_avg_ms", 0),
            duration_seconds=data.get("duration_seconds", 0),
            status=data.get("status", "UNKNOWN")
        )
    except subprocess.TimeoutExpired:
        print("  Node.js benchmark timed out")
        return None
    except json.JSONDecodeError as e:
        print(f"  Node.js benchmark JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"  Node.js benchmark error: {e}")
        return None


def run_python_benchmark(host: str, port: int, workers: int, queries: int) -> Optional[ClientResult]:
    """Run Python native client benchmark."""
    available, path = check_python_available()
    if not available:
        print(f"  Python client: {path}")
        return None

    python_dir = REPO_ROOT / "geode-client-python"
    python_venv = python_dir / ".venv" / "bin" / "python"

    cmd = [
        str(python_venv), "benchmarks/benchmark.py",
        "--host", host,
        "--port", str(port),
        "--workers", str(workers),
        "--queries", str(queries),
        "--json"
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(python_dir),
            capture_output=True,
            text=True,
            timeout=600
        )

        if result.returncode != 0:
            print(f"  Python benchmark failed: {result.stderr}")
            return None

        data = json.loads(result.stdout.strip())
        return ClientResult(
            client_name="python",
            workers=data.get("workers", workers),
            queries_per_worker=data.get("queries_per_worker", queries),
            total_queries=data.get("total_queries", 0),
            successful_queries=data.get("successful_queries", 0),
            failed_queries=data.get("failed_queries", 0),
            throughput_qps=data.get("throughput_qps", 0),
            latency_p50_ms=data.get("latency_p50_ms", 0),
            latency_p95_ms=data.get("latency_p95_ms", 0),
            latency_p99_ms=data.get("latency_p99_ms", 0),
            latency_avg_ms=data.get("latency_avg_ms", 0),
            duration_seconds=data.get("duration_seconds", 0),
            status=data.get("status", "UNKNOWN")
        )
    except subprocess.TimeoutExpired:
        print("  Python benchmark timed out")
        return None
    except json.JSONDecodeError as e:
        print(f"  Python benchmark JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"  Python benchmark error: {e}")
        return None


def run_zig_benchmark(host: str, port: int, workers: int, queries: int) -> Optional[ClientResult]:
    """Run Zig native client benchmark."""
    available, path = check_zig_available()
    if not available:
        print(f"  Zig client: {path}")
        return None

    zig_dir = REPO_ROOT / "geode-client-zig"
    benchmark_binary = zig_dir / "zig-out" / "bin" / "benchmark"

    # Only build if binary doesn't exist
    if not benchmark_binary.exists():
        build_cmd = ["zig", "build", "benchmark"]
        try:
            build_result = subprocess.run(
                build_cmd,
                cwd=str(zig_dir),
                capture_output=True,
                text=True,
                timeout=300  # Increased timeout for initial build
            )
            if build_result.returncode != 0:
                print(f"  Zig build failed: {build_result.stderr}")
                return None
        except subprocess.TimeoutExpired:
            print(f"  Zig build error: Command '{''.join(build_cmd)}' timed out after 120 seconds")
            return None
        except Exception as e:
            print(f"  Zig build error: {e}")
            return None

    # Run the benchmark
    cmd = [
        str(benchmark_binary),
        "--host", host,
        "--port", str(port),
        "--workers", str(workers),
        "--queries", str(queries),
        "--json"
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600
        )

        if result.returncode != 0:
            print(f"  Zig benchmark failed: {result.stderr}")
            return None

        data = json.loads(result.stdout.strip())
        return ClientResult(
            client_name="zig",
            workers=data.get("workers", workers),
            queries_per_worker=data.get("queries_per_worker", queries),
            total_queries=data.get("total_queries", 0),
            successful_queries=data.get("successful_queries", 0),
            failed_queries=data.get("failed_queries", 0),
            throughput_qps=data.get("throughput_qps", 0),
            latency_p50_ms=data.get("latency_p50_ms", 0),
            latency_p95_ms=data.get("latency_p95_ms", 0),
            latency_p99_ms=data.get("latency_p99_ms", 0),
            latency_avg_ms=data.get("latency_avg_ms", 0),
            duration_seconds=data.get("duration_seconds", 0),
            status=data.get("status", "UNKNOWN")
        )
    except subprocess.TimeoutExpired:
        print("  Zig benchmark timed out")
        return None
    except json.JSONDecodeError as e:
        print(f"  Zig benchmark JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"  Zig benchmark error: {e}")
        return None


# =============================================================================
# Client Registry
# =============================================================================

CLIENT_BENCHMARKS = {
    "go": run_go_benchmark,
    "python": run_python_benchmark,
    "rust": run_rust_benchmark,
    "nodejs": run_nodejs_benchmark,
    "node": run_nodejs_benchmark,  # Alias
    "zig": run_zig_benchmark,
}

ALL_CLIENTS = ["go", "python", "rust", "nodejs", "zig"]


def check_client_availability() -> Dict[str, Tuple[bool, str]]:
    """Check which clients are available."""
    checks = {
        "go": check_go_available,
        "python": check_python_available,
        "rust": check_rust_available,
        "nodejs": check_nodejs_available,
        "zig": check_zig_available,
    }
    return {name: check() for name, check in checks.items()}


# =============================================================================
# Multi-Client Orchestrator
# =============================================================================

def run_multi_client_benchmark(
    clients: List[str],
    workers: int,
    queries: int,
    host: str,
    port: int,
    output_dir: Path,
) -> MultiClientResult:
    """
    Run benchmarks with multiple native clients in parallel.
    """
    print(f"\n{'='*70}")
    print("MULTI-CLIENT NATIVE BENCHMARK")
    print(f"{'='*70}")
    print(f"Clients: {', '.join(clients)}")
    print(f"Workers per client: {workers}")
    print(f"Queries per worker: {queries}")
    print(f"Total queries per client: {workers * queries:,}")
    print(f"Host: {host}:{port}")
    print()

    # Check client availability
    print("Checking client availability...")
    availability = check_client_availability()
    for name in clients:
        if name in availability:
            available, msg = availability[name]
            status = "OK" if available else f"NOT AVAILABLE: {msg}"
            print(f"  {name:8}: {status}")
    print()

    output_dir.mkdir(parents=True, exist_ok=True)
    client_results = []
    futures = {}

    start_time = time.monotonic()

    print("Running benchmarks...")
    with ThreadPoolExecutor(max_workers=len(clients)) as executor:
        for client in clients:
            if client not in CLIENT_BENCHMARKS:
                print(f"  Unknown client: {client}, skipping")
                continue

            # Check if available
            if client in availability:
                available, _ = availability[client]
                if not available:
                    print(f"  Skipping {client} (not available)")
                    continue

            benchmark_fn = CLIENT_BENCHMARKS[client]
            future = executor.submit(benchmark_fn, host, port, workers, queries)
            futures[future] = client
            print(f"  Started {client} benchmark")

        # Collect results
        for future in as_completed(futures):
            client_name = futures[future]
            try:
                result = future.result()
                if result:
                    client_results.append(result)
                    print(f"  {client_name}: {result.successful_queries:,} queries, {result.throughput_qps:,.0f} qps, p50={result.latency_p50_ms:.1f}ms")
                else:
                    print(f"  {client_name}: FAILED")
            except Exception as e:
                print(f"  {client_name} failed: {e}")

    total_duration = time.monotonic() - start_time

    # Aggregate results
    aggregate_throughput = sum(r.throughput_qps for r in client_results)
    aggregate_successful = sum(r.successful_queries for r in client_results)
    aggregate_failed = sum(r.failed_queries for r in client_results)
    aggregate_total = aggregate_successful + aggregate_failed
    total_workers = sum(r.workers for r in client_results)

    CLAIMED_MAX = 100_000
    achieved_pct = (aggregate_throughput / CLAIMED_MAX) * 100 if CLAIMED_MAX > 0 else 0

    if aggregate_throughput >= CLAIMED_MAX:
        status = "VERIFIED"
    elif aggregate_throughput >= 10_000:
        status = "EXCELLENT"
    elif aggregate_throughput >= 1_000:
        status = "GOOD"
    elif aggregate_throughput >= 100:
        status = "ACCEPTABLE"
    else:
        status = "LIMITED"

    return MultiClientResult(
        benchmark_name="multi_client_native_benchmark",
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
    print("MULTI-CLIENT NATIVE BENCHMARK RESULTS")
    print(f"{'='*70}")
    print(f"Timestamp: {result.timestamp}")
    print(f"Duration: {result.total_duration_seconds:.2f}s")
    print(f"Clients: {', '.join(result.clients_used)}")
    print(f"Total Workers: {result.total_workers}")
    print()
    print("PER-CLIENT RESULTS:")
    print(f"  {'Client':8} | {'Queries':>12} | {'Throughput':>12} | {'p50':>8} | {'p95':>8} | {'p99':>8} | {'Status':>10}")
    print(f"  {'-'*8} | {'-'*12} | {'-'*12} | {'-'*8} | {'-'*8} | {'-'*8} | {'-'*10}")
    for cr in result.client_results:
        print(f"  {cr['client_name']:8} | {cr['successful_queries']:>12,} | {cr['throughput_qps']:>10,.0f} qps | {cr['latency_p50_ms']:>6.1f}ms | {cr['latency_p95_ms']:>6.1f}ms | {cr['latency_p99_ms']:>6.1f}ms | {cr['status']:>10}")
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
        description="Multi-client native benchmark for Geode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available native clients:
  go      - Go client (geode-client-go)
  python  - Python client (geode-client-python)
  rust    - Rust client (geode-client-rust)
  nodejs  - Node.js client (geode-client-nodejs)
  zig     - Zig client (geode-client-zig)
  all     - All available clients

Examples:
  # Run with all available clients
  python multi_client_benchmark.py --clients all --workers 10 --queries 1000

  # Run with specific clients
  python multi_client_benchmark.py --clients go,rust --workers 20 --queries 5000

  # High-scale test
  python multi_client_benchmark.py --clients all --workers 100 --queries 10000
        """
    )
    parser.add_argument(
        "--clients", "-c",
        type=str,
        default="all",
        help="Comma-separated list of clients or 'all' (default: all)"
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=10,
        help="Workers (concurrent connections) per client (default: 10)"
    )
    parser.add_argument(
        "--queries", "-q",
        type=int,
        default=1000,
        help="Queries per worker (default: 1000)"
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
        help="Output directory for results"
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
        workers=args.workers,
        queries=args.queries,
        host=args.host,
        port=args.port,
        output_dir=Path(args.output_dir),
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

    # Exit with appropriate code (0 for ACCEPTABLE or better, 1 for LIMITED/FAILED)
    if result.status in ["VERIFIED", "EXCELLENT", "GOOD", "ACCEPTABLE"]:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
