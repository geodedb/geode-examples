#!/usr/bin/env python3
"""
Extract Testable Claims from Documentation

Scans documentation for testable claims (performance numbers, feature counts,
capability statements) and outputs them in a structured format.

CANARY: REQ=REQ-EXTRACT-CLAIMS-001; FEATURE="ClaimExtraction"; ASPECT=Tooling; STATUS=TESTED

Usage:
    python extract_claims.py --docs-path /path/to/docs --output claims.json
    python extract_claims.py --docs-path /path/to/docs --format csv
"""
import argparse
import json
import re
import csv
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


@dataclass
class ExtractedClaim:
    """Represents a testable claim extracted from documentation."""
    claim_id: str
    claim_text: str
    claim_type: str  # performance, feature, compliance, security, scalability
    source_file: str
    source_line: int
    numeric_value: Optional[float] = None
    unit: Optional[str] = None
    comparison: Optional[str] = None  # up_to, at_least, exactly, approximately
    canary_req: Optional[str] = None
    verification_status: str = "PENDING"
    extracted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# Patterns for extracting claims
CLAIM_PATTERNS = [
    # Performance claims: "up to X txn/sec", "X queries/second"
    {
        "pattern": r"up to\s+([\d,]+)\s*(\w+/sec(?:ond)?)",
        "type": "performance",
        "comparison": "up_to"
    },
    {
        "pattern": r"([\d,]+)\s*-\s*([\d,]+)\s*(\w+/sec(?:ond)?)",
        "type": "performance",
        "comparison": "range"
    },
    {
        "pattern": r"<\s*([\d.]+)\s*(ns|us|ms|s)\b",
        "type": "performance",
        "comparison": "less_than"
    },
    {
        "pattern": r"([\d.]+)x\s+(improvement|faster|speedup)",
        "type": "performance",
        "comparison": "multiplier"
    },
    # Feature counts: "50+ data types", "20+ algorithms"
    {
        "pattern": r"(\d+)\+\s+(data types|algorithms|index types|isolation levels)",
        "type": "feature",
        "comparison": "at_least"
    },
    {
        "pattern": r"(\d+)\s+(data types|algorithms|index types|isolation levels)",
        "type": "feature",
        "comparison": "exactly"
    },
    # Compliance claims: "100% compliance", "70/70 tests"
    {
        "pattern": r"(\d+)%\s+(GQL|ISO|compliance)",
        "type": "compliance",
        "comparison": "percentage"
    },
    {
        "pattern": r"(\d+)/(\d+)\s+(tests?|passing)",
        "type": "compliance",
        "comparison": "ratio"
    },
    # Scalability claims: "100M+ nodes", "10,000+ connections"
    {
        "pattern": r"([\d,]+)M\+?\s+(nodes|vertices)",
        "type": "scalability",
        "comparison": "at_least"
    },
    {
        "pattern": r"([\d,]+)B\+?\s+(relationships|edges)",
        "type": "scalability",
        "comparison": "at_least"
    },
    {
        "pattern": r"([\d,]+)\+?\s+(concurrent connections|connections)",
        "type": "scalability",
        "comparison": "at_least"
    },
    # Security claims
    {
        "pattern": r"(TLS\s*1\.3|AES-256|Argon2id|QUIC)",
        "type": "security",
        "comparison": "supports"
    },
    {
        "pattern": r"<\s*([\d.]+)%\s+overhead",
        "type": "security",
        "comparison": "less_than"
    },
]


def parse_numeric(value: str) -> float:
    """Parse numeric value, handling commas and suffixes."""
    value = value.replace(",", "")
    if value.endswith("M"):
        return float(value[:-1]) * 1_000_000
    if value.endswith("B"):
        return float(value[:-1]) * 1_000_000_000
    if value.endswith("K"):
        return float(value[:-1]) * 1_000
    return float(value)


def extract_claims_from_file(file_path: Path, base_path: Path) -> List[ExtractedClaim]:
    """Extract all claims from a single file."""
    claims = []
    claim_counter = {}

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
        return claims

    lines = content.split("\n")
    relative_path = str(file_path.relative_to(base_path))

    for line_num, line in enumerate(lines, 1):
        for pattern_info in CLAIM_PATTERNS:
            pattern = pattern_info["pattern"]
            claim_type = pattern_info["type"]
            comparison = pattern_info["comparison"]

            for match in re.finditer(pattern, line, re.IGNORECASE):
                # Generate unique claim ID
                if claim_type not in claim_counter:
                    claim_counter[claim_type] = 0
                claim_counter[claim_type] += 1

                claim_id = f"CLAIM-{claim_type.upper()[:4]}-{claim_counter[claim_type]:03d}"

                # Extract numeric value if present
                numeric_value = None
                unit = None
                groups = match.groups()

                if groups:
                    try:
                        numeric_value = parse_numeric(groups[0])
                        if len(groups) > 1:
                            unit = groups[1] if not groups[1].replace(",", "").replace(".", "").isdigit() else groups[-1]
                    except (ValueError, IndexError):
                        pass

                claim = ExtractedClaim(
                    claim_id=claim_id,
                    claim_text=match.group(0).strip(),
                    claim_type=claim_type,
                    source_file=relative_path,
                    source_line=line_num,
                    numeric_value=numeric_value,
                    unit=unit,
                    comparison=comparison
                )
                claims.append(claim)

    return claims


def extract_all_claims(docs_path: Path) -> List[ExtractedClaim]:
    """Extract claims from all documentation files."""
    all_claims = []

    # Scan markdown and text files
    patterns = ["**/*.md", "**/*.txt", "**/*.rst"]

    for pattern in patterns:
        for file_path in docs_path.glob(pattern):
            # Skip node_modules, vendor, etc.
            if any(part.startswith(".") or part in ["node_modules", "vendor", "__pycache__"]
                   for part in file_path.parts):
                continue

            claims = extract_claims_from_file(file_path, docs_path)
            all_claims.extend(claims)

    return all_claims


def deduplicate_claims(claims: List[ExtractedClaim]) -> List[ExtractedClaim]:
    """Remove duplicate claims (same text from different locations)."""
    seen = {}
    unique = []

    for claim in claims:
        key = (claim.claim_text.lower(), claim.claim_type)
        if key not in seen:
            seen[key] = claim
            unique.append(claim)

    return unique


def output_json(claims: List[ExtractedClaim], output_path: Path):
    """Output claims as JSON."""
    data = {
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "total_claims": len(claims),
        "claims_by_type": {},
        "claims": [asdict(c) for c in claims]
    }

    for claim in claims:
        if claim.claim_type not in data["claims_by_type"]:
            data["claims_by_type"][claim.claim_type] = 0
        data["claims_by_type"][claim.claim_type] += 1

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Extracted {len(claims)} claims to {output_path}")


def output_csv(claims: List[ExtractedClaim], output_path: Path):
    """Output claims as CSV."""
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Claim ID", "Type", "Claim Text", "Value", "Unit",
            "Comparison", "Source File", "Line", "Status"
        ])

        for claim in claims:
            writer.writerow([
                claim.claim_id,
                claim.claim_type,
                claim.claim_text,
                claim.numeric_value or "",
                claim.unit or "",
                claim.comparison or "",
                claim.source_file,
                claim.source_line,
                claim.verification_status
            ])

    print(f"Extracted {len(claims)} claims to {output_path}")


def output_markdown(claims: List[ExtractedClaim], output_path: Path):
    """Output claims as Markdown table."""
    with open(output_path, "w") as f:
        f.write("# Extracted Claims\n\n")
        f.write(f"*Generated: {datetime.now(timezone.utc).isoformat()}*\n\n")
        f.write(f"**Total Claims: {len(claims)}**\n\n")

        # Group by type
        by_type = {}
        for claim in claims:
            if claim.claim_type not in by_type:
                by_type[claim.claim_type] = []
            by_type[claim.claim_type].append(claim)

        for claim_type, type_claims in sorted(by_type.items()):
            f.write(f"## {claim_type.title()} Claims ({len(type_claims)})\n\n")
            f.write("| Claim ID | Claim | Value | Source | Status |\n")
            f.write("|----------|-------|-------|--------|--------|\n")

            for claim in type_claims:
                value = f"{claim.numeric_value} {claim.unit or ''}" if claim.numeric_value else "-"
                source = f"`{claim.source_file}:{claim.source_line}`"
                f.write(f"| {claim.claim_id} | {claim.claim_text} | {value} | {source} | {claim.verification_status} |\n")

            f.write("\n")

    print(f"Extracted {len(claims)} claims to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Extract testable claims from documentation")
    parser.add_argument("--docs-path", "-d", type=Path, required=True,
                        help="Path to documentation directory")
    parser.add_argument("--output", "-o", type=Path, default=Path("claims.json"),
                        help="Output file path")
    parser.add_argument("--format", "-f", choices=["json", "csv", "markdown"],
                        default="json", help="Output format")
    parser.add_argument("--dedupe", action="store_true",
                        help="Remove duplicate claims")

    args = parser.parse_args()

    if not args.docs_path.exists():
        print(f"Error: Documentation path does not exist: {args.docs_path}", file=sys.stderr)
        sys.exit(1)

    # Extract claims
    claims = extract_all_claims(args.docs_path)

    if args.dedupe:
        original_count = len(claims)
        claims = deduplicate_claims(claims)
        print(f"Deduplicated: {original_count} -> {len(claims)} claims")

    # Output
    if args.format == "json":
        output_json(claims, args.output)
    elif args.format == "csv":
        output_csv(claims, args.output)
    elif args.format == "markdown":
        output_markdown(claims, args.output)

    # Print summary
    print("\nClaims by type:")
    by_type = {}
    for claim in claims:
        by_type[claim.claim_type] = by_type.get(claim.claim_type, 0) + 1
    for claim_type, count in sorted(by_type.items()):
        print(f"  {claim_type}: {count}")


if __name__ == "__main__":
    main()
