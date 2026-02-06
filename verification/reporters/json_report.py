#!/usr/bin/env python3
"""
JSON Verification Report Generator

Generates a comprehensive JSON report of all verification results.

CANARY: REQ=REQ-REPORT-JSON-001; FEATURE="JSONReport"; ASPECT=Reporting; STATUS=TESTED

Usage:
    python json_report.py --results-dir ./reports --output verification_report.json
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def load_json_file(path: Path) -> Dict[str, Any]:
    """Load a JSON file, returning empty dict on error."""
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load {path}: {e}", file=sys.stderr)
        return {}


def collect_pytest_results(results_dir: Path) -> Dict[str, Any]:
    """Collect pytest JSON results."""
    results = {
        "total_tests": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
        "test_files": []
    }

    # Look for pytest JSON reports
    for json_file in results_dir.glob("*.json"):
        if "pytest" in json_file.name or "test" in json_file.name:
            data = load_json_file(json_file)

            if "summary" in data:
                summary = data["summary"]
                results["total_tests"] += summary.get("total", 0)
                results["passed"] += summary.get("passed", 0)
                results["failed"] += summary.get("failed", 0)
                results["skipped"] += summary.get("skipped", 0)
                results["errors"] += summary.get("error", 0)

            if "tests" in data:
                results["test_files"].append({
                    "file": json_file.name,
                    "test_count": len(data["tests"])
                })

    return results


def collect_benchmark_results(results_dir: Path) -> List[Dict[str, Any]]:
    """Collect benchmark results."""
    benchmarks = []

    for json_file in results_dir.glob("**/perf*.json"):
        data = load_json_file(json_file)
        if data:
            benchmarks.append({
                "file": json_file.name,
                "benchmark_name": data.get("benchmark_name", "unknown"),
                "throughput": data.get("throughput_qps") or data.get("throughput_ops"),
                "status": data.get("status", "UNKNOWN"),
                "timestamp": data.get("timestamp")
            })

    for json_file in results_dir.glob("**/scale*.json"):
        data = load_json_file(json_file)
        if data:
            benchmarks.append({
                "file": json_file.name,
                "benchmark_name": data.get("benchmark_name", "scale_test"),
                "nodes_created": data.get("nodes_created") or data.get("total_nodes"),
                "status": data.get("status", "UNKNOWN"),
                "timestamp": data.get("timestamp")
            })

    return benchmarks


def load_claims_registry(docs_dir: Path) -> Dict[str, Any]:
    """Parse the claims registry markdown file."""
    registry_path = docs_dir / "CLAIMS_REGISTRY.md"
    if not registry_path.exists():
        return {"claims": [], "summary": {}}

    content = registry_path.read_text()

    # Extract summary statistics from the markdown table
    claims_summary = {
        "total": 0,
        "verified": 0,
        "partial": 0,
        "pending": 0,
        "unverified": 0
    }

    # Look for the summary table
    import re
    summary_match = re.search(r'\*\*Total\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|\s*\*\*(\d+)\*\*', content)
    if summary_match:
        claims_summary["total"] = int(summary_match.group(1))
        claims_summary["verified"] = int(summary_match.group(2))

    # Count status occurrences
    claims_summary["verified"] = content.count("| VERIFIED |")
    claims_summary["partial"] = content.count("| PARTIAL |")
    claims_summary["pending"] = content.count("| PENDING |")
    claims_summary["unverified"] = content.count("| UNVERIFIED |")
    claims_summary["total"] = (claims_summary["verified"] + claims_summary["partial"] +
                               claims_summary["pending"] + claims_summary["unverified"])

    return {
        "summary": claims_summary,
        "verification_rate": (claims_summary["verified"] + claims_summary["partial"]) /
                             claims_summary["total"] if claims_summary["total"] > 0 else 0
    }


def generate_report(results_dir: Path, docs_dir: Path) -> Dict[str, Any]:
    """Generate the complete verification report."""
    report = {
        "report_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "geode_version": "0.1.4+",

        "summary": {
            "overall_status": "UNKNOWN",
            "verification_rate": 0.0,
            "test_pass_rate": 0.0,
            "claims_verified": 0,
            "claims_total": 0
        },

        "test_results": {},
        "benchmark_results": [],
        "claims_registry": {},
        "recommendations": []
    }

    # Collect test results
    test_results = collect_pytest_results(results_dir)
    report["test_results"] = test_results

    if test_results["total_tests"] > 0:
        report["summary"]["test_pass_rate"] = test_results["passed"] / test_results["total_tests"]

    # Collect benchmark results
    report["benchmark_results"] = collect_benchmark_results(results_dir)

    # Load claims registry
    claims = load_claims_registry(docs_dir)
    report["claims_registry"] = claims

    if claims.get("summary", {}).get("total", 0) > 0:
        summary = claims["summary"]
        report["summary"]["claims_total"] = summary["total"]
        report["summary"]["claims_verified"] = summary["verified"] + summary["partial"]
        report["summary"]["verification_rate"] = claims.get("verification_rate", 0)

    # Determine overall status
    verification_rate = report["summary"]["verification_rate"]
    test_pass_rate = report["summary"]["test_pass_rate"]

    if verification_rate >= 0.9 and test_pass_rate >= 0.95:
        report["summary"]["overall_status"] = "VERIFIED"
    elif verification_rate >= 0.7 and test_pass_rate >= 0.80:
        report["summary"]["overall_status"] = "PARTIAL"
    elif verification_rate >= 0.5:
        report["summary"]["overall_status"] = "IN_PROGRESS"
    else:
        report["summary"]["overall_status"] = "NEEDS_ATTENTION"

    # Generate recommendations
    if test_results["failed"] > 0:
        report["recommendations"].append(f"Fix {test_results['failed']} failing tests")

    if claims.get("summary", {}).get("pending", 0) > 0:
        report["recommendations"].append(
            f"Run verification for {claims['summary']['pending']} pending claims"
        )

    if claims.get("summary", {}).get("unverified", 0) > 0:
        report["recommendations"].append(
            f"Create tests for {claims['summary']['unverified']} unverified claims"
        )

    return report


def main():
    parser = argparse.ArgumentParser(description="Generate JSON verification report")
    parser.add_argument("--results-dir", "-r", type=Path, default=Path("reports"),
                        help="Directory containing test results")
    parser.add_argument("--docs-dir", "-d", type=Path, default=Path("docs"),
                        help="Directory containing documentation")
    parser.add_argument("--output", "-o", type=Path, default=Path("verification_report.json"),
                        help="Output file path")

    args = parser.parse_args()

    print("Generating verification report...")

    report = generate_report(args.results_dir, args.docs_dir)

    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Report saved to {args.output}")
    print(f"\nSummary:")
    print(f"  Overall status: {report['summary']['overall_status']}")
    print(f"  Verification rate: {report['summary']['verification_rate']:.1%}")
    print(f"  Test pass rate: {report['summary']['test_pass_rate']:.1%}")
    print(f"  Claims: {report['summary']['claims_verified']}/{report['summary']['claims_total']}")

    if report["recommendations"]:
        print(f"\nRecommendations:")
        for rec in report["recommendations"]:
            print(f"  - {rec}")


if __name__ == "__main__":
    main()
