#!/usr/bin/env python3
"""
Verification Badge Generator

Generates SVG badges showing verification status for use in README files.

CANARY: REQ=REQ-REPORT-BADGE-001; FEATURE="BadgeGenerator"; ASPECT=Reporting; STATUS=TESTED

Usage:
    python badge_generator.py --json-report verification_report.json --output public/badge.svg
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, Tuple


# SVG badge template
BADGE_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="20" role="img" aria-label="{label}: {value}">
  <title>{label}: {value}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r">
    <rect width="{width}" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_width}" height="20" fill="#555"/>
    <rect x="{label_width}" width="{value_width}" height="20" fill="{color}"/>
    <rect width="{width}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-rendering="geometricPrecision" font-size="110">
    <text aria-hidden="true" x="{label_x}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)">{label}</text>
    <text x="{label_x}" y="140" transform="scale(.1)" fill="#fff">{label}</text>
    <text aria-hidden="true" x="{value_x}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)">{value}</text>
    <text x="{value_x}" y="140" transform="scale(.1)" fill="#fff">{value}</text>
  </g>
</svg>"""


def get_status_color(status: str) -> str:
    """Get color for status."""
    colors = {
        "VERIFIED": "#22c55e",      # Green
        "PARTIAL": "#eab308",        # Yellow
        "IN_PROGRESS": "#3b82f6",   # Blue
        "NEEDS_ATTENTION": "#ef4444", # Red
        "UNKNOWN": "#6b7280"        # Gray
    }
    return colors.get(status, "#6b7280")


def get_percentage_color(pct: float) -> str:
    """Get color based on percentage."""
    if pct >= 90:
        return "#22c55e"  # Green
    elif pct >= 70:
        return "#eab308"  # Yellow
    elif pct >= 50:
        return "#f97316"  # Orange
    else:
        return "#ef4444"  # Red


def calculate_text_width(text: str) -> int:
    """Estimate text width in pixels."""
    # Rough approximation: ~6 pixels per character
    return len(text) * 6 + 10


def generate_badge(label: str, value: str, color: str) -> str:
    """Generate an SVG badge."""
    label_width = calculate_text_width(label)
    value_width = calculate_text_width(value)
    total_width = label_width + value_width

    return BADGE_TEMPLATE.format(
        width=total_width,
        label=label,
        value=value,
        color=color,
        label_width=label_width,
        value_width=value_width,
        label_x=(label_width / 2) * 10,
        value_x=(label_width + value_width / 2) * 10
    )


def generate_status_badge(report: Dict[str, Any]) -> str:
    """Generate verification status badge."""
    status = report.get("summary", {}).get("overall_status", "UNKNOWN")
    color = get_status_color(status)
    return generate_badge("verification", status.lower().replace("_", " "), color)


def generate_rate_badge(report: Dict[str, Any]) -> str:
    """Generate verification rate badge."""
    rate = report.get("summary", {}).get("verification_rate", 0)
    pct = rate * 100
    color = get_percentage_color(pct)
    return generate_badge("verified", f"{pct:.0f}%", color)


def generate_tests_badge(report: Dict[str, Any]) -> str:
    """Generate test pass rate badge."""
    tests = report.get("test_results", {})
    passed = tests.get("passed", 0)
    total = tests.get("total_tests", 0)

    if total > 0:
        pct = (passed / total) * 100
        color = get_percentage_color(pct)
        value = f"{passed}/{total}"
    else:
        color = "#6b7280"
        value = "N/A"

    return generate_badge("tests", value, color)


def generate_claims_badge(report: Dict[str, Any]) -> str:
    """Generate claims verified badge."""
    summary = report.get("summary", {})
    verified = summary.get("claims_verified", 0)
    total = summary.get("claims_total", 0)

    if total > 0:
        pct = (verified / total) * 100
        color = get_percentage_color(pct)
    else:
        color = "#6b7280"

    return generate_badge("claims", f"{verified}/{total}", color)


def main():
    parser = argparse.ArgumentParser(description="Generate verification badges")
    parser.add_argument("--json-report", "-j", type=Path, required=True,
                        help="JSON report file")
    parser.add_argument("--output-dir", "-o", type=Path, default=Path("public"),
                        help="Output directory for badges")
    parser.add_argument("--type", "-t", choices=["status", "rate", "tests", "claims", "all"],
                        default="all", help="Type of badge to generate")

    args = parser.parse_args()

    if not args.json_report.exists():
        print(f"Error: Report file not found: {args.json_report}", file=sys.stderr)
        sys.exit(1)

    with open(args.json_report) as f:
        report = json.load(f)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    badges = {
        "status": ("badge-status.svg", generate_status_badge),
        "rate": ("badge-rate.svg", generate_rate_badge),
        "tests": ("badge-tests.svg", generate_tests_badge),
        "claims": ("badge-claims.svg", generate_claims_badge),
    }

    if args.type == "all":
        types_to_generate = badges.keys()
    else:
        types_to_generate = [args.type]

    for badge_type in types_to_generate:
        filename, generator = badges[badge_type]
        svg = generator(report)
        output_path = args.output_dir / filename

        with open(output_path, "w") as f:
            f.write(svg)

        print(f"Generated {output_path}")

    print("\nUsage in README.md:")
    print("```markdown")
    print("![Verification Status](public/badge-status.svg)")
    print("![Verified Claims](public/badge-claims.svg)")
    print("![Test Pass Rate](public/badge-tests.svg)")
    print("```")


if __name__ == "__main__":
    main()
