#!/bin/bash
# extract_all_claims.sh - Extract testable claims from geodedb.com documentation
#
# Usage: ./scripts/extract_all_claims.sh [--output FILE]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

DOCS_DIR="${PROJECT_ROOT}/../geodedb.com/content"
OUTPUT_FILE="${PROJECT_ROOT}/docs/CLAIMS_REGISTRY.md"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [ ! -d "$DOCS_DIR" ]; then
    echo "Error: Documentation directory not found at $DOCS_DIR"
    echo "Please ensure geodedb.com repository is cloned alongside geode-examples"
    exit 1
fi

echo "Extracting claims from documentation..."

# Initialize output file
cat > "$OUTPUT_FILE" << 'EOF'
# Geode Claims Registry

This document tracks all verifiable claims made in the geodedb.com documentation.
Generated automatically by `scripts/extract_all_claims.sh`.

## Claim Categories

- **COMPLIANCE**: Standards compliance claims (ISO GQL, etc.)
- **PERFORMANCE**: Performance metrics and benchmarks
- **SECURITY**: Security features and capabilities
- **SCALABILITY**: Scalability limits and capabilities
- **FEATURE**: Feature existence claims
- **CLIENT**: Client library claims

## Status Legend

- **VERIFIED**: Claim verified by automated tests
- **PENDING**: Test exists but not yet run
- **UNVERIFIED**: No test exists yet
- **FAILED**: Claim could not be verified

---

## Extracted Claims

| ID | Category | Claim | Source | Status | Test |
|----|----------|-------|--------|--------|------|
EOF

# Extract numeric claims (percentages, counts, rates)
echo "Extracting numeric claims..."

claim_id=1

# Pattern: X% compliance/coverage
grep -roh '[0-9]\+\(\.[0-9]\+\)\?%\s*\(compliance\|coverage\|pass\)' "$DOCS_DIR" 2>/dev/null | \
    sort -u | while read -r claim; do
    echo "| CLAIM-$(printf '%03d' $claim_id) | COMPLIANCE | $claim | docs | UNVERIFIED | - |" >> "$OUTPUT_FILE"
    claim_id=$((claim_id + 1))
done

# Pattern: up to X,XXX txn/sec
grep -roh 'up to [0-9,]\+\s*txn/sec' "$DOCS_DIR" 2>/dev/null | \
    sort -u | while read -r claim; do
    echo "| CLAIM-$(printf '%03d' $claim_id) | PERFORMANCE | $claim | docs | UNVERIFIED | - |" >> "$OUTPUT_FILE"
    claim_id=$((claim_id + 1))
done

# Pattern: <Xns or <Xms latency
grep -roh '<[0-9]\+\(ns\|ms\|us\)' "$DOCS_DIR" 2>/dev/null | \
    sort -u | while read -r claim; do
    echo "| CLAIM-$(printf '%03d' $claim_id) | PERFORMANCE | $claim latency | docs | UNVERIFIED | - |" >> "$OUTPUT_FILE"
    claim_id=$((claim_id + 1))
done

# Pattern: X.XXx improvement
grep -roh '[0-9]\+\(\.[0-9]\+\)\?x\s*improvement' "$DOCS_DIR" 2>/dev/null | \
    sort -u | while read -r claim; do
    echo "| CLAIM-$(printf '%03d' $claim_id) | PERFORMANCE | $claim | docs | UNVERIFIED | - |" >> "$OUTPUT_FILE"
    claim_id=$((claim_id + 1))
done

# Pattern: X+ types/indexes/algorithms
grep -roh '[0-9]\++\s*\(types\|indexes\|algorithms\|shards\|connections\)' "$DOCS_DIR" 2>/dev/null | \
    sort -u | while read -r claim; do
    echo "| CLAIM-$(printf '%03d' $claim_id) | FEATURE | $claim | docs | UNVERIFIED | - |" >> "$OUTPUT_FILE"
    claim_id=$((claim_id + 1))
done

# Pattern: X isolation levels
grep -roh '[0-9]\+\s*isolation levels' "$DOCS_DIR" 2>/dev/null | \
    sort -u | while read -r claim; do
    echo "| CLAIM-$(printf '%03d' $claim_id) | FEATURE | $claim | docs | UNVERIFIED | - |" >> "$OUTPUT_FILE"
    claim_id=$((claim_id + 1))
done

# Add summary
cat >> "$OUTPUT_FILE" << 'EOF'

---

## Summary Statistics

| Category | Total | Verified | Pending | Failed |
|----------|-------|----------|---------|--------|
| COMPLIANCE | - | - | - | - |
| PERFORMANCE | - | - | - | - |
| SECURITY | - | - | - | - |
| SCALABILITY | - | - | - | - |
| FEATURE | - | - | - | - |
| CLIENT | - | - | - | - |
| **TOTAL** | - | - | - | - |

---

*Last updated: $(date -Iseconds)*
EOF

echo ""
echo "Claims extracted to: $OUTPUT_FILE"
echo ""
echo "Next steps:"
echo "1. Review extracted claims for accuracy"
echo "2. Create verification tests for each claim"
echo "3. Link claims to CANARY markers in geode codebase"
