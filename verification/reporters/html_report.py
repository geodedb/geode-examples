#!/usr/bin/env python3
"""
HTML Verification Report Generator

Generates a user-friendly HTML report of verification results.

CANARY: REQ=REQ-REPORT-HTML-001; FEATURE="HTMLReport"; ASPECT=Reporting; STATUS=TESTED

Usage:
    python html_report.py --json-report verification_report.json --output public/index.html
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Geode Verification Report</title>
    <style>
        :root {{
            --color-verified: #22c55e;
            --color-partial: #eab308;
            --color-pending: #3b82f6;
            --color-failed: #ef4444;
            --color-bg: #0f172a;
            --color-card: #1e293b;
            --color-text: #f8fafc;
            --color-muted: #94a3b8;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--color-bg);
            color: var(--color-text);
            line-height: 1.6;
            padding: 2rem;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        header {{
            text-align: center;
            margin-bottom: 3rem;
        }}

        h1 {{
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
        }}

        .subtitle {{
            color: var(--color-muted);
            font-size: 1.1rem;
        }}

        .status-badge {{
            display: inline-block;
            padding: 0.5rem 1.5rem;
            border-radius: 9999px;
            font-weight: bold;
            font-size: 1.25rem;
            margin: 1rem 0;
        }}

        .status-VERIFIED {{ background: var(--color-verified); }}
        .status-PARTIAL {{ background: var(--color-partial); color: #000; }}
        .status-IN_PROGRESS {{ background: var(--color-pending); }}
        .status-NEEDS_ATTENTION {{ background: var(--color-failed); }}

        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}

        .card {{
            background: var(--color-card);
            border-radius: 12px;
            padding: 1.5rem;
        }}

        .card h3 {{
            color: var(--color-muted);
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }}

        .card .value {{
            font-size: 2.5rem;
            font-weight: bold;
        }}

        .card .detail {{
            color: var(--color-muted);
            font-size: 0.875rem;
        }}

        .progress-bar {{
            height: 8px;
            background: #334155;
            border-radius: 4px;
            margin-top: 1rem;
            overflow: hidden;
        }}

        .progress-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s ease;
        }}

        .progress-verified {{ background: var(--color-verified); }}
        .progress-partial {{ background: var(--color-partial); }}
        .progress-pending {{ background: var(--color-pending); }}

        section {{
            margin-bottom: 3rem;
        }}

        section h2 {{
            font-size: 1.5rem;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid #334155;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th, td {{
            text-align: left;
            padding: 0.75rem 1rem;
            border-bottom: 1px solid #334155;
        }}

        th {{
            color: var(--color-muted);
            font-weight: 500;
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
        }}

        .status-cell {{
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: bold;
        }}

        .status-cell.VERIFIED {{ background: var(--color-verified); }}
        .status-cell.PARTIAL {{ background: var(--color-partial); color: #000; }}
        .status-cell.PENDING {{ background: var(--color-pending); }}
        .status-cell.FAILED {{ background: var(--color-failed); }}

        .recommendations {{
            background: #1e3a5f;
            border-radius: 8px;
            padding: 1.5rem;
            border-left: 4px solid var(--color-pending);
        }}

        .recommendations h3 {{
            margin-bottom: 1rem;
        }}

        .recommendations ul {{
            list-style: none;
        }}

        .recommendations li {{
            padding: 0.5rem 0;
            padding-left: 1.5rem;
            position: relative;
        }}

        .recommendations li::before {{
            content: "→";
            position: absolute;
            left: 0;
            color: var(--color-pending);
        }}

        footer {{
            text-align: center;
            color: var(--color-muted);
            font-size: 0.875rem;
            margin-top: 3rem;
            padding-top: 2rem;
            border-top: 1px solid #334155;
        }}

        footer a {{
            color: var(--color-pending);
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Geode Verification Report</h1>
            <p class="subtitle">Automated claim verification for geodedb.com documentation</p>
            <div class="status-badge status-{overall_status}">{overall_status}</div>
            <p class="subtitle">Generated: {generated_at}</p>
        </header>

        <div class="grid">
            <div class="card">
                <h3>Verification Rate</h3>
                <div class="value">{verification_rate:.1%}</div>
                <div class="detail">{claims_verified} of {claims_total} claims verified</div>
                <div class="progress-bar">
                    <div class="progress-fill progress-verified" style="width: {verification_pct}%"></div>
                </div>
            </div>

            <div class="card">
                <h3>Test Pass Rate</h3>
                <div class="value">{test_pass_rate:.1%}</div>
                <div class="detail">{tests_passed} of {tests_total} tests passed</div>
                <div class="progress-bar">
                    <div class="progress-fill progress-verified" style="width: {test_pass_pct}%"></div>
                </div>
            </div>

            <div class="card">
                <h3>Benchmarks Run</h3>
                <div class="value">{benchmark_count}</div>
                <div class="detail">Performance verification tests</div>
            </div>

            <div class="card">
                <h3>Claims Categories</h3>
                <div class="value">7</div>
                <div class="detail">Compliance, Performance, Security, Features, Clients, Scalability, Coverage</div>
            </div>
        </div>

        {recommendations_section}

        <section>
            <h2>Benchmark Results</h2>
            <table>
                <thead>
                    <tr>
                        <th>Benchmark</th>
                        <th>Result</th>
                        <th>Status</th>
                        <th>Timestamp</th>
                    </tr>
                </thead>
                <tbody>
                    {benchmark_rows}
                </tbody>
            </table>
        </section>

        <section>
            <h2>Claims Summary by Category</h2>
            <table>
                <thead>
                    <tr>
                        <th>Category</th>
                        <th>Total</th>
                        <th>Verified</th>
                        <th>Partial</th>
                        <th>Pending</th>
                    </tr>
                </thead>
                <tbody>
                    {claims_rows}
                </tbody>
            </table>
        </section>

        <footer>
            <p>
                Geode Examples Verification Suite<br>
                <a href="https://geodedb.com">geodedb.com</a> |
                <a href="https://gitlab.com/devnw/codepros/geode/geode-examples">GitLab Repository</a>
            </p>
        </footer>
    </div>
</body>
</html>
"""


def format_benchmark_rows(benchmarks: list) -> str:
    """Format benchmark results as HTML table rows."""
    if not benchmarks:
        return "<tr><td colspan='4'>No benchmark results available</td></tr>"

    rows = []
    for b in benchmarks:
        name = b.get("benchmark_name", "Unknown")
        result = b.get("throughput") or b.get("nodes_created") or "-"
        if isinstance(result, (int, float)):
            result = f"{result:,.0f}"
        status = b.get("status", "UNKNOWN")
        timestamp = b.get("timestamp", "-")
        if timestamp and "T" in str(timestamp):
            timestamp = timestamp.split("T")[0]

        rows.append(f"""
            <tr>
                <td>{name}</td>
                <td>{result}</td>
                <td><span class="status-cell {status}">{status}</span></td>
                <td>{timestamp}</td>
            </tr>
        """)

    return "\n".join(rows)


def format_claims_rows() -> str:
    """Format claims summary as HTML table rows."""
    # These are from the CLAIMS_REGISTRY.md
    categories = [
        ("Standards Compliance", 7, 7, 0, 0),
        ("Performance", 7, 1, 4, 2),
        ("Scalability", 4, 1, 1, 2),
        ("Security", 8, 8, 0, 0),
        ("Features", 6, 5, 0, 1),
        ("Client Libraries", 9, 7, 2, 0),
        ("Test Coverage", 3, 0, 0, 1),
    ]

    rows = []
    for cat, total, verified, partial, pending in categories:
        rows.append(f"""
            <tr>
                <td>{cat}</td>
                <td>{total}</td>
                <td>{verified}</td>
                <td>{partial}</td>
                <td>{pending}</td>
            </tr>
        """)

    return "\n".join(rows)


def format_recommendations(recommendations: list) -> str:
    """Format recommendations section."""
    if not recommendations:
        return ""

    items = "\n".join(f"<li>{r}</li>" for r in recommendations)
    return f"""
        <section class="recommendations">
            <h3>Recommendations</h3>
            <ul>
                {items}
            </ul>
        </section>
    """


def generate_html(report: Dict[str, Any]) -> str:
    """Generate HTML report from JSON data."""
    summary = report.get("summary", {})

    # Calculate percentages for progress bars
    verification_rate = summary.get("verification_rate", 0)
    test_pass_rate = summary.get("test_pass_rate", 0)

    tests = report.get("test_results", {})
    tests_passed = tests.get("passed", 0)
    tests_total = tests.get("total_tests", 0) or 1  # Avoid division by zero

    html = HTML_TEMPLATE.format(
        overall_status=summary.get("overall_status", "UNKNOWN"),
        generated_at=report.get("generated_at", datetime.now(timezone.utc).isoformat())[:19],
        verification_rate=verification_rate,
        verification_pct=verification_rate * 100,
        claims_verified=summary.get("claims_verified", 0),
        claims_total=summary.get("claims_total", 0),
        test_pass_rate=test_pass_rate,
        test_pass_pct=test_pass_rate * 100,
        tests_passed=tests_passed,
        tests_total=tests_total,
        benchmark_count=len(report.get("benchmark_results", [])),
        benchmark_rows=format_benchmark_rows(report.get("benchmark_results", [])),
        claims_rows=format_claims_rows(),
        recommendations_section=format_recommendations(report.get("recommendations", []))
    )

    return html


def main():
    parser = argparse.ArgumentParser(description="Generate HTML verification report")
    parser.add_argument("--json-report", "-j", type=Path,
                        help="JSON report file (from json_report.py)")
    parser.add_argument("--results-dir", "-r", type=Path, default=Path("reports"),
                        help="Directory containing test results (if no JSON report)")
    parser.add_argument("--output", "-o", type=Path, default=Path("public/index.html"),
                        help="Output HTML file path")

    args = parser.parse_args()

    # Load or generate JSON report
    if args.json_report and args.json_report.exists():
        with open(args.json_report) as f:
            report = json.load(f)
    else:
        # Generate from results directory
        from json_report import generate_report
        report = generate_report(args.results_dir, Path("docs"))

    # Generate HTML
    html = generate_html(report)

    # Write output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        f.write(html)

    print(f"HTML report saved to {args.output}")


if __name__ == "__main__":
    main()
