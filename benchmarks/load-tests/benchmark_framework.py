#!/usr/bin/env python3
"""
Statistical Benchmark Framework for Geode

This framework provides statistically rigorous benchmarking with:
- Multiple runs for statistical significance
- Raw data collection and storage
- Statistical analysis (mean, std dev, confidence intervals, percentiles)
- System information capture
- Pre-run system load measurement
- Publication-ready reports in JSON and Markdown

CANARY: REQ=REQ-PERF-FRAMEWORK-001; FEATURE="BenchmarkFramework"; ASPECT=Performance; STATUS=TESTED

Usage:
    # Run benchmark with 5 iterations for statistical significance
    python benchmark_framework.py --runs 5 --workers 50 --duration 60

    # Full statistical benchmark with system info
    python benchmark_framework.py --runs 10 --workers 100 --duration 120 --output-dir results/

    # Quick validation run
    python benchmark_framework.py --runs 3 --workers 20 --duration 30
"""
import argparse
import json
import math
import os
import platform
import psutil
import shutil
import statistics
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Any
import socket


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class SystemInfo:
    """System information for benchmark context."""
    hostname: str
    platform: str
    platform_release: str
    platform_version: str
    architecture: str
    processor: str
    cpu_count_physical: int
    cpu_count_logical: int
    cpu_freq_mhz: Optional[float]
    memory_total_gb: float
    memory_available_gb: float
    python_version: str
    timestamp: str


@dataclass
class SystemLoad:
    """System load at a point in time."""
    timestamp: str
    cpu_percent: float
    cpu_percent_per_core: List[float]
    memory_percent: float
    memory_used_gb: float
    memory_available_gb: float
    load_avg_1m: float
    load_avg_5m: float
    load_avg_15m: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_io_sent_mb: float
    network_io_recv_mb: float


@dataclass
class SingleRunResult:
    """Result from a single benchmark run."""
    run_number: int
    start_time: str
    end_time: str
    duration_seconds: float
    total_queries: int
    successful_queries: int
    failed_queries: int
    throughput_qps: float
    latencies_ms: List[float]  # Raw latency samples
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    latency_avg_ms: float
    latency_min_ms: float
    latency_max_ms: float
    latency_std_ms: float
    error_rate: float


@dataclass
class StatisticalSummary:
    """Statistical summary across multiple runs."""
    num_runs: int
    throughput_mean_qps: float
    throughput_std_qps: float
    throughput_min_qps: float
    throughput_max_qps: float
    throughput_ci_95_lower: float
    throughput_ci_95_upper: float
    latency_p50_mean_ms: float
    latency_p50_std_ms: float
    latency_p99_mean_ms: float
    latency_p99_std_ms: float
    success_rate_mean: float
    success_rate_std: float
    coefficient_of_variation: float  # CV = std/mean * 100


@dataclass
class BenchmarkReport:
    """Complete benchmark report for publication."""
    benchmark_name: str
    benchmark_version: str
    timestamp: str
    system_info: Dict
    pre_run_load: Dict
    post_run_load: Dict
    configuration: Dict
    raw_results: List[Dict]
    statistical_summary: Dict
    claimed_performance: Dict
    verification_status: str
    notes: List[str]


# =============================================================================
# System Information Collection
# =============================================================================

def get_system_info() -> SystemInfo:
    """Collect comprehensive system information."""
    cpu_freq = psutil.cpu_freq()
    memory = psutil.virtual_memory()

    return SystemInfo(
        hostname=socket.gethostname(),
        platform=platform.system(),
        platform_release=platform.release(),
        platform_version=platform.version(),
        architecture=platform.machine(),
        processor=platform.processor() or "Unknown",
        cpu_count_physical=psutil.cpu_count(logical=False) or 0,
        cpu_count_logical=psutil.cpu_count(logical=True) or 0,
        cpu_freq_mhz=cpu_freq.current if cpu_freq else None,
        memory_total_gb=memory.total / (1024**3),
        memory_available_gb=memory.available / (1024**3),
        python_version=platform.python_version(),
        timestamp=datetime.now(timezone.utc).isoformat()
    )


def get_system_load() -> SystemLoad:
    """Capture current system load."""
    memory = psutil.virtual_memory()
    disk_io = psutil.disk_io_counters()
    net_io = psutil.net_io_counters()
    load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)

    return SystemLoad(
        timestamp=datetime.now(timezone.utc).isoformat(),
        cpu_percent=psutil.cpu_percent(interval=1),
        cpu_percent_per_core=psutil.cpu_percent(interval=0.1, percpu=True),
        memory_percent=memory.percent,
        memory_used_gb=memory.used / (1024**3),
        memory_available_gb=memory.available / (1024**3),
        load_avg_1m=load_avg[0],
        load_avg_5m=load_avg[1],
        load_avg_15m=load_avg[2],
        disk_io_read_mb=disk_io.read_bytes / (1024**2) if disk_io else 0,
        disk_io_write_mb=disk_io.write_bytes / (1024**2) if disk_io else 0,
        network_io_sent_mb=net_io.bytes_sent / (1024**2) if net_io else 0,
        network_io_recv_mb=net_io.bytes_recv / (1024**2) if net_io else 0
    )


# =============================================================================
# Benchmark Workers
# =============================================================================

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
    """Thread-safe latency collector with all samples."""
    def __init__(self):
        self._samples = []
        self._lock = threading.Lock()

    def add(self, latency_ms: float):
        with self._lock:
            self._samples.append(latency_ms)

    def add_batch(self, latencies: List[float]):
        with self._lock:
            self._samples.extend(latencies)

    @property
    def samples(self):
        with self._lock:
            return list(self._samples)


def benchmark_worker(
    worker_id: int,
    stop_event: threading.Event,
    successful: AtomicCounter,
    failed: AtomicCounter,
    latencies: LatencyCollector,
    batch_size: int,
    host: str,
    port: int,
    use_docker: bool
):
    """Worker that runs queries continuously until stopped."""
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
                per_query = latency / batch_size
                latencies.add_batch([per_query] * batch_size)
            else:
                failed.add(batch_size)

        except Exception:
            failed.add(batch_size)


def run_single_benchmark(
    run_number: int,
    workers: int,
    duration: int,
    batch_size: int,
    host: str,
    port: int,
    use_docker: bool,
    verbose: bool = False
) -> SingleRunResult:
    """Execute a single benchmark run."""
    if verbose:
        print(f"  Run {run_number}: Starting {workers} workers for {duration}s...")

    stop_event = threading.Event()
    successful = AtomicCounter()
    failed = AtomicCounter()
    latencies = LatencyCollector()

    threads = []
    start_time = datetime.now(timezone.utc)

    for i in range(workers):
        t = threading.Thread(
            target=benchmark_worker,
            args=(i, stop_event, successful, failed, latencies, batch_size, host, port, use_docker),
            daemon=True
        )
        t.start()
        threads.append(t)

    # Run for specified duration
    benchmark_start = time.monotonic()
    time.sleep(duration)
    stop_event.set()

    # Wait for workers to finish
    for t in threads:
        t.join(timeout=2.0)

    actual_duration = time.monotonic() - benchmark_start
    end_time = datetime.now(timezone.utc)

    # Collect results
    total_successful = successful.value
    total_failed = failed.value
    total_queries = total_successful + total_failed
    throughput = total_successful / actual_duration if actual_duration > 0 else 0
    error_rate = total_failed / total_queries if total_queries > 0 else 0

    # Calculate latency statistics
    samples = latencies.samples
    if samples:
        sorted_samples = sorted(samples)
        n = len(sorted_samples)
        p50 = sorted_samples[int(n * 0.50)]
        p95 = sorted_samples[int(n * 0.95)]
        p99 = sorted_samples[min(int(n * 0.99), n - 1)]
        avg = statistics.mean(samples)
        std = statistics.stdev(samples) if len(samples) > 1 else 0
        min_lat = min(samples)
        max_lat = max(samples)
    else:
        p50 = p95 = p99 = avg = std = min_lat = max_lat = 0
        samples = []

    if verbose:
        print(f"  Run {run_number}: {total_successful:,} queries, {throughput:,.0f} qps, p99={p99:.1f}ms")

    return SingleRunResult(
        run_number=run_number,
        start_time=start_time.isoformat(),
        end_time=end_time.isoformat(),
        duration_seconds=actual_duration,
        total_queries=total_queries,
        successful_queries=total_successful,
        failed_queries=total_failed,
        throughput_qps=throughput,
        latencies_ms=samples[:10000],  # Store up to 10k samples for analysis
        latency_p50_ms=p50,
        latency_p95_ms=p95,
        latency_p99_ms=p99,
        latency_avg_ms=avg,
        latency_min_ms=min_lat,
        latency_max_ms=max_lat,
        latency_std_ms=std,
        error_rate=error_rate
    )


# =============================================================================
# Statistical Analysis
# =============================================================================

def calculate_confidence_interval(data: List[float], confidence: float = 0.95) -> tuple:
    """Calculate confidence interval for the mean."""
    n = len(data)
    if n < 2:
        return (0, 0)

    mean = statistics.mean(data)
    std = statistics.stdev(data)
    stderr = std / math.sqrt(n)

    # t-value for 95% CI (approximation for large n)
    if confidence == 0.95:
        if n >= 30:
            t_value = 1.96
        elif n >= 10:
            t_value = 2.262
        else:
            t_value = 2.776
    else:
        t_value = 1.96  # Default to 95%

    margin = t_value * stderr
    return (mean - margin, mean + margin)


def calculate_statistical_summary(results: List[SingleRunResult]) -> StatisticalSummary:
    """Calculate comprehensive statistics across multiple runs."""
    throughputs = [r.throughput_qps for r in results]
    p50s = [r.latency_p50_ms for r in results]
    p99s = [r.latency_p99_ms for r in results]
    success_rates = [1 - r.error_rate for r in results]

    throughput_mean = statistics.mean(throughputs)
    throughput_std = statistics.stdev(throughputs) if len(throughputs) > 1 else 0
    ci_lower, ci_upper = calculate_confidence_interval(throughputs)

    cv = (throughput_std / throughput_mean * 100) if throughput_mean > 0 else 0

    return StatisticalSummary(
        num_runs=len(results),
        throughput_mean_qps=throughput_mean,
        throughput_std_qps=throughput_std,
        throughput_min_qps=min(throughputs),
        throughput_max_qps=max(throughputs),
        throughput_ci_95_lower=ci_lower,
        throughput_ci_95_upper=ci_upper,
        latency_p50_mean_ms=statistics.mean(p50s),
        latency_p50_std_ms=statistics.stdev(p50s) if len(p50s) > 1 else 0,
        latency_p99_mean_ms=statistics.mean(p99s),
        latency_p99_std_ms=statistics.stdev(p99s) if len(p99s) > 1 else 0,
        success_rate_mean=statistics.mean(success_rates),
        success_rate_std=statistics.stdev(success_rates) if len(success_rates) > 1 else 0,
        coefficient_of_variation=cv
    )


# =============================================================================
# Report Generation
# =============================================================================

def generate_markdown_report(report: BenchmarkReport, output_path: Path):
    """Generate a publication-ready Markdown report."""
    md = []
    md.append(f"# {report.benchmark_name} Benchmark Report")
    md.append("")
    md.append(f"**Generated:** {report.timestamp}")
    md.append(f"**Benchmark Version:** {report.benchmark_version}")
    md.append("")

    # System Information
    md.append("## System Information")
    md.append("")
    sys_info = report.system_info
    md.append(f"| Property | Value |")
    md.append(f"|----------|-------|")
    md.append(f"| Hostname | {sys_info['hostname']} |")
    md.append(f"| Platform | {sys_info['platform']} {sys_info['platform_release']} |")
    md.append(f"| Architecture | {sys_info['architecture']} |")
    md.append(f"| CPU | {sys_info['processor']} |")
    md.append(f"| CPU Cores | {sys_info['cpu_count_physical']} physical, {sys_info['cpu_count_logical']} logical |")
    md.append(f"| Memory | {sys_info['memory_total_gb']:.1f} GB total |")
    md.append(f"| Python | {sys_info['python_version']} |")
    md.append("")

    # Pre-run System Load
    md.append("## Pre-Run System Load")
    md.append("")
    pre_load = report.pre_run_load
    md.append(f"| Metric | Value |")
    md.append(f"|--------|-------|")
    md.append(f"| CPU Usage | {pre_load['cpu_percent']:.1f}% |")
    md.append(f"| Memory Usage | {pre_load['memory_percent']:.1f}% |")
    md.append(f"| Load Average (1m) | {pre_load['load_avg_1m']:.2f} |")
    md.append(f"| Load Average (5m) | {pre_load['load_avg_5m']:.2f} |")
    md.append(f"| Memory Available | {pre_load['memory_available_gb']:.1f} GB |")
    md.append("")

    # Configuration
    md.append("## Benchmark Configuration")
    md.append("")
    config = report.configuration
    md.append(f"| Parameter | Value |")
    md.append(f"|-----------|-------|")
    for key, value in config.items():
        md.append(f"| {key} | {value} |")
    md.append("")

    # Statistical Summary
    md.append("## Results Summary")
    md.append("")
    stats = report.statistical_summary
    md.append(f"**Number of Runs:** {stats['num_runs']}")
    md.append("")
    md.append("### Throughput")
    md.append("")
    md.append(f"| Statistic | Value |")
    md.append(f"|-----------|-------|")
    md.append(f"| Mean | {stats['throughput_mean_qps']:,.0f} qps |")
    md.append(f"| Std Dev | {stats['throughput_std_qps']:,.1f} qps |")
    md.append(f"| Min | {stats['throughput_min_qps']:,.0f} qps |")
    md.append(f"| Max | {stats['throughput_max_qps']:,.0f} qps |")
    md.append(f"| 95% CI | [{stats['throughput_ci_95_lower']:,.0f}, {stats['throughput_ci_95_upper']:,.0f}] qps |")
    md.append(f"| CV | {stats['coefficient_of_variation']:.1f}% |")
    md.append("")

    md.append("### Latency")
    md.append("")
    md.append(f"| Percentile | Mean | Std Dev |")
    md.append(f"|------------|------|---------|")
    md.append(f"| P50 | {stats['latency_p50_mean_ms']:.2f} ms | {stats['latency_p50_std_ms']:.2f} ms |")
    md.append(f"| P99 | {stats['latency_p99_mean_ms']:.2f} ms | {stats['latency_p99_std_ms']:.2f} ms |")
    md.append("")

    md.append("### Reliability")
    md.append("")
    md.append(f"| Metric | Value |")
    md.append(f"|--------|-------|")
    md.append(f"| Success Rate | {stats['success_rate_mean']*100:.2f}% (+/- {stats['success_rate_std']*100:.2f}%) |")
    md.append("")

    # Per-Run Results
    md.append("## Individual Run Results")
    md.append("")
    md.append(f"| Run | Queries | Throughput (qps) | P50 (ms) | P99 (ms) | Success Rate |")
    md.append(f"|-----|---------|------------------|----------|----------|--------------|")
    for r in report.raw_results:
        success_rate = (1 - r['error_rate']) * 100
        md.append(f"| {r['run_number']} | {r['successful_queries']:,} | {r['throughput_qps']:,.0f} | {r['latency_p50_ms']:.1f} | {r['latency_p99_ms']:.1f} | {success_rate:.1f}% |")
    md.append("")

    # Claim Verification
    md.append("## Claim Verification")
    md.append("")
    claimed = report.claimed_performance
    md.append(f"| Claim | Target | Achieved | Status |")
    md.append(f"|-------|--------|----------|--------|")
    md.append(f"| Max Throughput | {claimed['max_throughput_qps']:,} qps | {stats['throughput_mean_qps']:,.0f} qps | {report.verification_status} |")
    md.append("")

    # Notes
    if report.notes:
        md.append("## Notes")
        md.append("")
        for note in report.notes:
            md.append(f"- {note}")
        md.append("")

    # Post-run Load
    md.append("## Post-Run System Load")
    md.append("")
    post_load = report.post_run_load
    md.append(f"| Metric | Value |")
    md.append(f"|--------|-------|")
    md.append(f"| CPU Usage | {post_load['cpu_percent']:.1f}% |")
    md.append(f"| Memory Usage | {post_load['memory_percent']:.1f}% |")
    md.append(f"| Load Average (1m) | {post_load['load_avg_1m']:.2f} |")
    md.append("")

    output_path.write_text("\n".join(md))


# =============================================================================
# Main Benchmark Runner
# =============================================================================

def run_benchmark_suite(
    num_runs: int,
    workers: int,
    duration: int,
    batch_size: int,
    host: str,
    port: int,
    use_docker: bool,
    warmup_duration: int = 10,
    cooldown_duration: int = 5,
    verbose: bool = True
) -> BenchmarkReport:
    """
    Run a complete benchmark suite with multiple runs and statistical analysis.
    """
    print(f"\n{'='*70}")
    print("GEODE STATISTICAL BENCHMARK SUITE")
    print(f"{'='*70}")

    # Collect system info
    print("\nCollecting system information...")
    system_info = get_system_info()
    print(f"  Host: {system_info.hostname}")
    print(f"  Platform: {system_info.platform} {system_info.platform_release}")
    print(f"  CPU: {system_info.cpu_count_physical} cores ({system_info.cpu_count_logical} logical)")
    print(f"  Memory: {system_info.memory_total_gb:.1f} GB")

    # Pre-run system load
    print("\nMeasuring pre-run system load...")
    time.sleep(2)  # Let system settle
    pre_run_load = get_system_load()
    print(f"  CPU: {pre_run_load.cpu_percent:.1f}%")
    print(f"  Memory: {pre_run_load.memory_percent:.1f}%")
    print(f"  Load Average: {pre_run_load.load_avg_1m:.2f}")

    # Warmup run
    if warmup_duration > 0:
        print(f"\nWarmup run ({warmup_duration}s)...")
        run_single_benchmark(0, workers, warmup_duration, batch_size, host, port, use_docker, verbose=False)
        print("  Warmup complete")
        time.sleep(cooldown_duration)

    # Main benchmark runs
    print(f"\nRunning {num_runs} benchmark iterations...")
    print(f"  Workers: {workers}")
    print(f"  Duration per run: {duration}s")
    print(f"  Batch size: {batch_size}")
    print()

    results = []
    for i in range(1, num_runs + 1):
        result = run_single_benchmark(i, workers, duration, batch_size, host, port, use_docker, verbose)
        results.append(result)

        if i < num_runs:
            print(f"  Cooldown ({cooldown_duration}s)...")
            time.sleep(cooldown_duration)

    # Post-run system load
    print("\nMeasuring post-run system load...")
    post_run_load = get_system_load()
    print(f"  CPU: {post_run_load.cpu_percent:.1f}%")
    print(f"  Memory: {post_run_load.memory_percent:.1f}%")

    # Calculate statistics
    print("\nCalculating statistics...")
    stats = calculate_statistical_summary(results)

    # Determine verification status
    CLAIMED_MAX = 100_000
    if stats.throughput_mean_qps >= CLAIMED_MAX:
        status = "VERIFIED"
    elif stats.throughput_mean_qps >= 10_000:
        status = "PARTIAL"
    elif stats.throughput_mean_qps >= 1_000:
        status = "BASELINE"
    else:
        status = "LIMITED"

    # Build report
    notes = []
    if stats.coefficient_of_variation > 10:
        notes.append(f"High variability (CV={stats.coefficient_of_variation:.1f}%) - results may be unstable")
    if pre_run_load.cpu_percent > 50:
        notes.append(f"High pre-run CPU load ({pre_run_load.cpu_percent:.1f}%) may affect results")
    if use_docker:
        notes.append("Benchmark uses Docker subprocess calls - native clients will achieve higher throughput")

    report = BenchmarkReport(
        benchmark_name="Geode High-Throughput Benchmark",
        benchmark_version="1.0.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
        system_info=asdict(system_info),
        pre_run_load=asdict(pre_run_load),
        post_run_load=asdict(post_run_load),
        configuration={
            "num_runs": num_runs,
            "workers": workers,
            "duration_seconds": duration,
            "batch_size": batch_size,
            "host": f"{host}:{port}",
            "use_docker": use_docker,
            "warmup_duration": warmup_duration,
            "cooldown_duration": cooldown_duration
        },
        raw_results=[asdict(r) for r in results],
        statistical_summary=asdict(stats),
        claimed_performance={"max_throughput_qps": CLAIMED_MAX},
        verification_status=status,
        notes=notes
    )

    return report


def print_summary(report: BenchmarkReport):
    """Print a summary of benchmark results."""
    stats = report.statistical_summary

    print(f"\n{'='*70}")
    print("BENCHMARK SUMMARY")
    print(f"{'='*70}")
    print(f"Runs: {stats['num_runs']}")
    print()
    print("THROUGHPUT:")
    print(f"  Mean:     {stats['throughput_mean_qps']:>10,.0f} qps")
    print(f"  Std Dev:  {stats['throughput_std_qps']:>10,.1f} qps")
    print(f"  95% CI:   [{stats['throughput_ci_95_lower']:,.0f}, {stats['throughput_ci_95_upper']:,.0f}] qps")
    print(f"  CV:       {stats['coefficient_of_variation']:>10.1f}%")
    print()
    print("LATENCY:")
    print(f"  P50:      {stats['latency_p50_mean_ms']:>10.2f} ms (+/- {stats['latency_p50_std_ms']:.2f})")
    print(f"  P99:      {stats['latency_p99_mean_ms']:>10.2f} ms (+/- {stats['latency_p99_std_ms']:.2f})")
    print()
    print(f"STATUS: {report.verification_status}")
    print(f"{'='*70}")


def main():
    parser = argparse.ArgumentParser(
        description="Statistical benchmark framework for Geode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick validation (3 runs)
  python benchmark_framework.py --runs 3 --workers 20 --duration 30

  # Standard benchmark (5 runs)
  python benchmark_framework.py --runs 5 --workers 50 --duration 60

  # Publication-quality benchmark (10 runs)
  python benchmark_framework.py --runs 10 --workers 100 --duration 120 --output-dir results/
        """
    )
    parser.add_argument("--runs", "-n", type=int, default=5, help="Number of benchmark runs (default: 5)")
    parser.add_argument("--workers", "-w", type=int, default=50, help="Parallel workers (default: 50)")
    parser.add_argument("--duration", "-d", type=int, default=60, help="Duration per run in seconds (default: 60)")
    parser.add_argument("--batch-size", "-b", type=int, default=10, help="Queries per batch (default: 10)")
    parser.add_argument("--host", type=str, default="localhost", help="Geode host (default: localhost)")
    parser.add_argument("--port", type=int, default=3141, help="Geode port (default: 3141)")
    parser.add_argument("--output-dir", "-o", type=str, default="reports/benchmark", help="Output directory")
    parser.add_argument("--no-docker", action="store_true", help="Don't use docker compose")
    parser.add_argument("--warmup", type=int, default=10, help="Warmup duration in seconds (default: 10)")
    parser.add_argument("--cooldown", type=int, default=5, help="Cooldown between runs (default: 5)")
    parser.add_argument("--quiet", "-q", action="store_true", help="Quiet mode")

    args = parser.parse_args()

    # Run benchmark suite
    report = run_benchmark_suite(
        num_runs=args.runs,
        workers=args.workers,
        duration=args.duration,
        batch_size=args.batch_size,
        host=args.host,
        port=args.port,
        use_docker=not args.no_docker,
        warmup_duration=args.warmup,
        cooldown_duration=args.cooldown,
        verbose=not args.quiet
    )

    # Print summary
    print_summary(report)

    # Save reports
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # JSON report (complete data)
    json_path = output_dir / f"benchmark_{timestamp}.json"
    with open(json_path, 'w') as f:
        json.dump(asdict(report) if hasattr(report, '__dataclass_fields__') else report.__dict__, f, indent=2, default=str)
    print(f"\nJSON report: {json_path}")

    # Markdown report (publication-ready)
    md_path = output_dir / f"benchmark_{timestamp}.md"
    generate_markdown_report(report, md_path)
    print(f"Markdown report: {md_path}")

    # Raw data (for further analysis)
    raw_path = output_dir / f"benchmark_{timestamp}_raw.json"
    raw_data = {
        "configuration": report.configuration,
        "runs": report.raw_results
    }
    with open(raw_path, 'w') as f:
        json.dump(raw_data, f, indent=2)
    print(f"Raw data: {raw_path}")

    sys.exit(0)


if __name__ == "__main__":
    main()
