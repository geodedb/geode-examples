#!/usr/bin/env python3
"""
CANARY Marker Linker

Links documentation claims to CANARY markers in the Geode codebase.
Produces a cross-reference report showing coverage.

CANARY: REQ=REQ-CANARY-LINK-001; FEATURE="CanaryLinker"; ASPECT=Tooling; STATUS=TESTED

Usage:
    python canary_linker.py --geode-path ../geode --claims claims.json --output crossref.json
"""
import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set


@dataclass
class CanaryMarker:
    """Represents a CANARY marker found in code."""
    req_id: str
    feature: str
    aspect: str
    status: str
    file_path: str
    line_number: int


@dataclass
class CrossReference:
    """Cross-reference between claim and CANARY marker."""
    claim_id: str
    claim_text: str
    canary_req: Optional[str]
    canary_feature: Optional[str]
    canary_status: Optional[str]
    canary_file: Optional[str]
    linked: bool
    confidence: float  # 0.0 to 1.0


# CANARY marker pattern
# Format: CANARY: REQ=REQ-XXX-001; FEATURE="FeatureName"; ASPECT=Category; STATUS=TESTED
CANARY_PATTERN = re.compile(
    r'CANARY:\s*REQ=([^;]+);\s*FEATURE="([^"]+)";\s*ASPECT=([^;]+);\s*STATUS=(\w+)',
    re.IGNORECASE
)


def extract_canary_markers(geode_path: Path) -> Dict[str, CanaryMarker]:
    """Extract all CANARY markers from the Geode codebase."""
    markers = {}

    # File extensions to scan
    extensions = {".zig", ".py", ".go", ".rs", ".md", ".gql", ".sql", ".js", ".ts"}

    for file_path in geode_path.rglob("*"):
        # Skip hidden files and common non-source directories
        if any(part.startswith(".") or part in ["node_modules", "vendor", "target", "zig-cache", "zig-out"]
               for part in file_path.parts):
            continue

        if file_path.suffix not in extensions:
            continue

        if not file_path.is_file():
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for line_num, line in enumerate(content.split("\n"), 1):
            match = CANARY_PATTERN.search(line)
            if match:
                req_id = match.group(1).strip()
                marker = CanaryMarker(
                    req_id=req_id,
                    feature=match.group(2).strip(),
                    aspect=match.group(3).strip(),
                    status=match.group(4).strip(),
                    file_path=str(file_path.relative_to(geode_path)),
                    line_number=line_num
                )
                markers[req_id] = marker

    return markers


def compute_similarity(text1: str, text2: str) -> float:
    """Compute simple word-based similarity between two texts."""
    words1 = set(re.findall(r'\w+', text1.lower()))
    words2 = set(re.findall(r'\w+', text2.lower()))

    if not words1 or not words2:
        return 0.0

    intersection = words1 & words2
    union = words1 | words2

    return len(intersection) / len(union)


def find_best_match(claim_text: str, markers: Dict[str, CanaryMarker],
                    threshold: float = 0.3) -> Optional[tuple]:
    """Find the best matching CANARY marker for a claim."""
    best_match = None
    best_score = threshold

    for req_id, marker in markers.items():
        # Compare claim text with feature name
        score = compute_similarity(claim_text, marker.feature)

        # Boost score for exact keyword matches
        claim_lower = claim_text.lower()
        feature_lower = marker.feature.lower()

        # Direct substring match
        if feature_lower in claim_lower or claim_lower in feature_lower:
            score += 0.3

        # Key terms boost
        key_terms = ["throughput", "latency", "vector", "transaction", "index",
                     "security", "tde", "rls", "audit", "connection", "shard"]
        for term in key_terms:
            if term in claim_lower and term in feature_lower:
                score += 0.2

        if score > best_score:
            best_score = score
            best_match = (req_id, marker, min(score, 1.0))

    return best_match


def link_claims_to_markers(claims: List[dict],
                           markers: Dict[str, CanaryMarker]) -> List[CrossReference]:
    """Link claims to their corresponding CANARY markers."""
    crossrefs = []

    for claim in claims:
        claim_id = claim.get("claim_id", "UNKNOWN")
        claim_text = claim.get("claim_text", "")

        # Check if claim already has a canary_req assigned
        existing_req = claim.get("canary_req")
        if existing_req and existing_req in markers:
            marker = markers[existing_req]
            crossref = CrossReference(
                claim_id=claim_id,
                claim_text=claim_text,
                canary_req=existing_req,
                canary_feature=marker.feature,
                canary_status=marker.status,
                canary_file=marker.file_path,
                linked=True,
                confidence=1.0
            )
        else:
            # Try to find a match
            match = find_best_match(claim_text, markers)
            if match:
                req_id, marker, confidence = match
                crossref = CrossReference(
                    claim_id=claim_id,
                    claim_text=claim_text,
                    canary_req=req_id,
                    canary_feature=marker.feature,
                    canary_status=marker.status,
                    canary_file=marker.file_path,
                    linked=True,
                    confidence=confidence
                )
            else:
                crossref = CrossReference(
                    claim_id=claim_id,
                    claim_text=claim_text,
                    canary_req=None,
                    canary_feature=None,
                    canary_status=None,
                    canary_file=None,
                    linked=False,
                    confidence=0.0
                )

        crossrefs.append(crossref)

    return crossrefs


def generate_report(crossrefs: List[CrossReference],
                    markers: Dict[str, CanaryMarker]) -> dict:
    """Generate a cross-reference report."""
    linked = [c for c in crossrefs if c.linked]
    unlinked = [c for c in crossrefs if not c.linked]

    # Find orphaned markers (not linked to any claim)
    linked_reqs = {c.canary_req for c in linked if c.canary_req}
    orphaned_markers = [m for req_id, m in markers.items() if req_id not in linked_reqs]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_claims": len(crossrefs),
            "linked_claims": len(linked),
            "unlinked_claims": len(unlinked),
            "link_rate": len(linked) / len(crossrefs) if crossrefs else 0,
            "total_canary_markers": len(markers),
            "orphaned_markers": len(orphaned_markers),
            "coverage": len(linked_reqs) / len(markers) if markers else 0
        },
        "crossreferences": [asdict(c) for c in crossrefs],
        "unlinked_claims": [asdict(c) for c in unlinked],
        "orphaned_markers": [asdict(m) for m in orphaned_markers]
    }


def main():
    parser = argparse.ArgumentParser(description="Link claims to CANARY markers")
    parser.add_argument("--geode-path", "-g", type=Path, required=True,
                        help="Path to Geode codebase")
    parser.add_argument("--claims", "-c", type=Path,
                        help="Claims JSON file (from extract_claims.py)")
    parser.add_argument("--output", "-o", type=Path, default=Path("crossref.json"),
                        help="Output file path")
    parser.add_argument("--markers-only", action="store_true",
                        help="Only extract and list CANARY markers")

    args = parser.parse_args()

    if not args.geode_path.exists():
        print(f"Error: Geode path does not exist: {args.geode_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning {args.geode_path} for CANARY markers...")
    markers = extract_canary_markers(args.geode_path)
    print(f"Found {len(markers)} CANARY markers")

    if args.markers_only:
        # Output markers only
        output = {
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "total_markers": len(markers),
            "markers": [asdict(m) for m in markers.values()]
        }
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2)
        print(f"Markers saved to {args.output}")

        # Print summary by aspect
        by_aspect = {}
        for marker in markers.values():
            by_aspect[marker.aspect] = by_aspect.get(marker.aspect, 0) + 1
        print("\nMarkers by aspect:")
        for aspect, count in sorted(by_aspect.items()):
            print(f"  {aspect}: {count}")
        return

    # Load claims
    if not args.claims or not args.claims.exists():
        print("Error: Claims file required for linking", file=sys.stderr)
        sys.exit(1)

    with open(args.claims) as f:
        claims_data = json.load(f)

    claims = claims_data.get("claims", [])
    print(f"Loaded {len(claims)} claims")

    # Link claims to markers
    print("Linking claims to CANARY markers...")
    crossrefs = link_claims_to_markers(claims, markers)

    # Generate report
    report = generate_report(crossrefs, markers)

    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nCross-reference report saved to {args.output}")
    print(f"\nSummary:")
    print(f"  Total claims: {report['summary']['total_claims']}")
    print(f"  Linked claims: {report['summary']['linked_claims']}")
    print(f"  Link rate: {report['summary']['link_rate']:.1%}")
    print(f"  CANARY coverage: {report['summary']['coverage']:.1%}")


if __name__ == "__main__":
    main()
