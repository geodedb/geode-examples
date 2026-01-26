# Verification Tests

This directory contains tests that verify claims made in the Geode documentation.

## Purpose

The verification tests serve as **black-box validation** of ALL claims made in the
[geodedb.com](https://geodedb.com) documentation. Each test verifies a specific
claim by testing the actual Geode server behavior.

## Directory Structure

```
verification/
├── claims/              # Tests organized by claim category
│   ├── compliance/      # ISO GQL compliance claims
│   ├── performance/     # Performance metric claims
│   ├── security/        # Security feature claims
│   ├── scalability/     # Scalability claims
│   └── features/        # Feature existence claims
├── extractors/          # Tools to extract claims from docs
└── reporters/           # Report generation tools
```

## Claim Categories

### Compliance (`claims/compliance/`)
- ISO/IEC 39075:2024 GQL compliance (70/70 tests)
- Pattern matching syntax
- Aggregation support
- Set operations

### Performance (`claims/performance/`)
- Throughput claims (100k, 50k, 20k txn/sec)
- Latency claims (<50ns vector, <1ms local)
- I/O improvement claims (13.18x mmap)

### Security (`claims/security/`)
- TDE encryption (<1% overhead)
- TLS 1.3 only
- RLS policy evaluation
- Audit logging

### Scalability (`claims/scalability/`)
- Connection limits (10,000+)
- Shard support (up to 32)
- Data volume (100M+ nodes)

### Features (`claims/features/`)
- Data type count (50+)
- Index type count (6)
- Algorithm count (20+)
- Isolation levels (6)

## Running Verification Tests

### All Tests

```bash
pytest verification/claims/ -v
```

### By Category

```bash
pytest verification/claims/compliance/ -v
pytest verification/claims/performance/ -v
pytest verification/claims/security/ -v
```

### With Report

```bash
pytest verification/claims/ -v --junitxml=reports/verification.xml
```

## Writing Verification Tests

### Template

```python
"""
Verify claim: [Exact claim text from documentation]
Source: [Documentation page/section]
CANARY: REQ=[Requirement ID from geode codebase]
"""
import pytest

class TestClaimDescription:
    """Test class for the claim being verified."""

    def test_claim_verification(self, geode_client):
        """Verify the specific claim."""
        # Arrange: Set up test conditions

        # Act: Execute the operation being claimed

        # Assert: Verify the claim
        assert result meets claim, f"Claim failed: expected X, got Y"
```

### CANARY Markers

Always include CANARY markers to link claims to the geode codebase:

```python
# CANARY: REQ=REQ-PERF-001; FEATURE="ReadThroughput"; ASPECT=Performance; STATUS=TESTED
```

## Extracting Claims

### From Documentation

```bash
python extractors/extract_claims.py --source ../geodedb.com/content --output claims.json
```

### Cross-Reference with CANARY

```bash
python extractors/canary_linker.py --claims claims.json --geode ../geode
```

## Reporting

### Generate HTML Report

```bash
python reporters/html_report.py --results reports/ --output public/index.html
```

### Generate Badge

```bash
python reporters/badge_generator.py --results reports/ --output public/badge.svg
```

## CI/CD Integration

Tests run automatically on:
- Every merge request
- Main branch pushes
- Scheduled weekly runs (full benchmarks)

Results are published to GitLab Pages at the repository's pages URL.
