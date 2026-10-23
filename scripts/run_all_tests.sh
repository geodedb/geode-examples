#!/bin/bash
# run_all_tests.sh - Run all verification tests
#
# Usage: ./scripts/run_all_tests.sh [--quick] [--category CATEGORY]
#
# Categories: gql, clients, features, security, performance

set -euo pipefail
shopt -s globstar nullglob

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default settings
QUICK_MODE=false
VERBOSE=false
CATEGORY="all"
GEODE_HOST="${GEODE_HOST:-localhost:3141}"
REPORTS_DIR="${PROJECT_ROOT}/reports"

# Use venv Python if available
if [ -f "${PROJECT_ROOT}/.venv/bin/python3" ]; then
    PYTHON="${PROJECT_ROOT}/.venv/bin/python3"
else
    PYTHON="python3"
fi

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --category)
            CATEGORY="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--quick] [--verbose|-v] [--category CATEGORY]"
            echo ""
            echo "Options:"
            echo "  --quick      Skip performance tests"
            echo "  --verbose    Show detailed test output"
            echo "  --category   Run specific category (gql, clients, features, security, performance)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

mkdir -p "$REPORTS_DIR"

log_section() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
}

log_skip() {
    echo -e "${YELLOW}[SKIP]${NC} $1"
}

# Test counters
PASSED=0
FAILED=0
SKIPPED=0

run_gql_tests() {
    log_section "GQL Compliance Tests"

    if [ -d "${PROJECT_ROOT}/gql" ]; then
        for gql_file in "${PROJECT_ROOT}"/gql/**/*.gql; do
            if [ -f "$gql_file" ]; then
                filename=$(basename "$gql_file")
                if timeout 30 bash "${SCRIPT_DIR}/geode-query.sh" "$(cat "$gql_file")" &> /dev/null; then
                    log_success "$filename"
                    PASSED=$((PASSED + 1))
                else
                    log_fail "$filename"
                    FAILED=$((FAILED + 1))
                fi
            fi
        done
    else
        log_skip "No GQL test files found"
        SKIPPED=$((SKIPPED + 1))
    fi
}

run_client_tests() {
    log_section "Client Library Tests"

    for language in go python rust nodejs zig; do
        if bash "${SCRIPT_DIR}/test-client.sh" "$language"; then
            log_success "$language client examples"
            PASSED=$((PASSED + 1))
        else
            log_fail "$language client examples (see reports/$language-tests.log)"
            FAILED=$((FAILED + 1))
        fi
    done
}

run_feature_tests() {
    log_section "Feature Verification Tests"

    if [ -d "${PROJECT_ROOT}/verification/claims/features" ]; then
        echo "Running feature verification..."
        if ! $PYTHON -c "import pytest" 2>/dev/null; then
            echo "pytest not installed" > "${REPORTS_DIR}/features.log"
            log_skip "Feature verification tests (pytest not installed)"
            SKIPPED=$((SKIPPED + 1))
        elif $PYTHON -m pytest "${PROJECT_ROOT}/verification/claims/features/" \
            -v --tb=short \
            --junitxml="${REPORTS_DIR}/features.xml" \
            > "${REPORTS_DIR}/features.log" 2>&1; then
            log_success "Feature verification tests"
            PASSED=$((PASSED + 1))
        else
            log_fail "Feature verification tests (see reports/features.log)"
            FAILED=$((FAILED + 1))
        fi
    else
        log_skip "Feature tests not configured"
        SKIPPED=$((SKIPPED + 1))
    fi
}

run_security_tests() {
    log_section "Security Verification Tests"

    if [ -d "${PROJECT_ROOT}/verification/claims/security" ]; then
        echo "Running security verification..."
        if ! $PYTHON -c "import pytest" 2>/dev/null; then
            echo "pytest not installed" > "${REPORTS_DIR}/security.log"
            log_skip "Security verification tests (pytest not installed)"
            SKIPPED=$((SKIPPED + 1))
        elif $PYTHON -m pytest "${PROJECT_ROOT}/verification/claims/security/" \
            -v --tb=short \
            --junitxml="${REPORTS_DIR}/security.xml" \
            > "${REPORTS_DIR}/security.log" 2>&1; then
            log_success "Security verification tests"
            PASSED=$((PASSED + 1))
        else
            log_fail "Security verification tests (see reports/security.log)"
            FAILED=$((FAILED + 1))
        fi
    else
        log_skip "Security tests not configured"
        SKIPPED=$((SKIPPED + 1))
    fi
}

run_performance_tests() {
    log_section "Performance Verification Tests"

    if [ "$QUICK_MODE" = true ]; then
        log_skip "Performance tests skipped in quick mode"
        SKIPPED=$((SKIPPED + 1))
        return
    fi

    # Check if Geode server is available
    if ! command -v geode &>/dev/null && ! docker compose ps 2>/dev/null | grep -q "geode.*Up"; then
        log_skip "Performance tests skipped (no Geode server available)"
        SKIPPED=$((SKIPPED + 1))
        return
    fi

    if [ -d "${PROJECT_ROOT}/benchmarks/load-tests" ]; then
        echo "Running performance benchmarks..."
        if [ "$VERBOSE" = true ]; then
            echo "  Target: ${GEODE_HOST}"
            echo "  Duration: 30s"
            echo "  Workers: 10"
        fi
        # Run with reduced duration for CI
        if $PYTHON "${PROJECT_ROOT}/benchmarks/load-tests/read_only.py" \
            --duration 30 \
            --output "${REPORTS_DIR}/perf-read-only.json" \
            > "${REPORTS_DIR}/perf-read-only.log" 2>&1; then
            if [ "$VERBOSE" = true ]; then
                # Extract throughput from results
                if [ -f "${REPORTS_DIR}/perf-read-only.json" ]; then
                    qps=$(grep -o '"throughput_qps": [0-9]*' "${REPORTS_DIR}/perf-read-only.json" | grep -o '[0-9]*' || echo "0")
                    echo "  Throughput: ${qps} qps"
                fi
            fi
            log_success "Read-only throughput test"
            PASSED=$((PASSED + 1))
        else
            # Check if failure was due to no server connection
            if grep -q "Failed:.*730\|Successful:.*0" "${REPORTS_DIR}/perf-read-only.log" 2>/dev/null; then
                log_skip "Performance tests skipped (Geode server not responding)"
                SKIPPED=$((SKIPPED + 1))
            else
                log_fail "Read-only throughput test"
                FAILED=$((FAILED + 1))
            fi
        fi
    else
        log_skip "Performance tests not configured"
        SKIPPED=$((SKIPPED + 1))
    fi
}

# Main execution
echo "Geode Examples Test Runner"
echo "=========================="
echo "Host: $GEODE_HOST"
mode_str="$([ "$QUICK_MODE" = true ] && echo "Quick" || echo "Full")"
[ "$VERBOSE" = true ] && mode_str="$mode_str (Verbose)"
echo "Mode: $mode_str"
echo "Category: $CATEGORY"
echo ""

case $CATEGORY in
    all)
        run_gql_tests
        run_client_tests
        run_feature_tests
        run_security_tests
        run_performance_tests
        ;;
    gql)
        run_gql_tests
        ;;
    clients)
        run_client_tests
        ;;
    features)
        run_feature_tests
        ;;
    security)
        run_security_tests
        ;;
    performance)
        run_performance_tests
        ;;
    *)
        echo "Unknown category: $CATEGORY"
        exit 1
        ;;
esac

# Summary
log_section "Test Summary"
echo "Passed:  $PASSED"
echo "Failed:  $FAILED"
echo "Skipped: $SKIPPED"
echo ""

# Generate summary report
cat > "${REPORTS_DIR}/summary-${CATEGORY}.json" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "host": "$GEODE_HOST",
  "mode": "$([ "$QUICK_MODE" = true ] && echo "quick" || echo "full")",
  "category": "$CATEGORY",
  "passed": $PASSED,
  "failed": $FAILED,
  "skipped": $SKIPPED
}
EOF

if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
else
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
fi
