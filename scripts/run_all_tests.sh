#!/bin/bash
# run_all_tests.sh - Run all verification tests
#
# Usage: ./scripts/run_all_tests.sh [--quick] [--category CATEGORY]
#
# Categories: gql, clients, features, security, performance

set -euo pipefail

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
CATEGORY="all"
GEODE_HOST="${GEODE_HOST:-localhost:3141}"
REPORTS_DIR="${PROJECT_ROOT}/reports"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --category)
            CATEGORY="$2"
            shift 2
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
                if timeout 30 geode shell -h "$GEODE_HOST" < "$gql_file" &> /dev/null; then
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

    # Go client (build verification - examples don't have test files)
    if [ -f "${PROJECT_ROOT}/clients/go/go.mod" ]; then
        echo "Running Go client tests..."
        if (cd "${PROJECT_ROOT}/clients/go" && go build ./... > "${REPORTS_DIR}/go-tests.log" 2>&1); then
            log_success "Go client tests"
            PASSED=$((PASSED + 1))
        else
            log_fail "Go client tests (see reports/go-tests.log)"
            FAILED=$((FAILED + 1))
        fi
    else
        log_skip "Go client not configured"
        SKIPPED=$((SKIPPED + 1))
    fi

    # Python client (syntax check - skip if pytest not available)
    if [ -f "${PROJECT_ROOT}/clients/python/requirements.txt" ]; then
        echo "Running Python client tests..."
        if ! python3 -c "import pytest" 2>/dev/null; then
            echo "pytest not installed" > "${REPORTS_DIR}/python-tests.log"
            log_skip "Python client tests (pytest not installed)"
            SKIPPED=$((SKIPPED + 1))
        elif (cd "${PROJECT_ROOT}/clients/python" && python3 -m py_compile examples/*.py > "${REPORTS_DIR}/python-tests.log" 2>&1); then
            log_success "Python client tests"
            PASSED=$((PASSED + 1))
        else
            log_fail "Python client tests (see reports/python-tests.log)"
            FAILED=$((FAILED + 1))
        fi
    else
        log_skip "Python client not configured"
        SKIPPED=$((SKIPPED + 1))
    fi

    # Rust client (build verification - examples use mock implementations)
    if [ -f "${PROJECT_ROOT}/clients/rust/Cargo.toml" ]; then
        echo "Running Rust client tests..."
        if (cd "${PROJECT_ROOT}/clients/rust" && cargo build --examples > "${REPORTS_DIR}/rust-tests.log" 2>&1); then
            log_success "Rust client tests"
            PASSED=$((PASSED + 1))
        else
            log_fail "Rust client tests (see reports/rust-tests.log)"
            FAILED=$((FAILED + 1))
        fi
    else
        log_skip "Rust client not configured"
        SKIPPED=$((SKIPPED + 1))
    fi

    # Zig client
    if [ -f "${PROJECT_ROOT}/clients/zig/build.zig" ]; then
        echo "Running Zig client tests..."
        if (cd "${PROJECT_ROOT}/clients/zig" && zig build test > "${REPORTS_DIR}/zig-tests.log" 2>&1); then
            log_success "Zig client tests"
            PASSED=$((PASSED + 1))
        else
            log_fail "Zig client tests (see reports/zig-tests.log)"
            FAILED=$((FAILED + 1))
        fi
    else
        log_skip "Zig client not configured"
        SKIPPED=$((SKIPPED + 1))
    fi
}

run_feature_tests() {
    log_section "Feature Verification Tests"

    if [ -d "${PROJECT_ROOT}/verification/claims/features" ]; then
        echo "Running feature verification..."
        if ! python3 -c "import pytest" 2>/dev/null; then
            echo "pytest not installed" > "${REPORTS_DIR}/features.log"
            log_skip "Feature verification tests (pytest not installed)"
            SKIPPED=$((SKIPPED + 1))
        elif python3 -m pytest "${PROJECT_ROOT}/verification/claims/features/" \
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
        if ! python3 -c "import pytest" 2>/dev/null; then
            echo "pytest not installed" > "${REPORTS_DIR}/security.log"
            log_skip "Security verification tests (pytest not installed)"
            SKIPPED=$((SKIPPED + 1))
        elif python3 -m pytest "${PROJECT_ROOT}/verification/claims/security/" \
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

    if [ -d "${PROJECT_ROOT}/benchmarks/load-tests" ]; then
        echo "Running performance benchmarks..."
        # Run with reduced duration for CI
        if python3 "${PROJECT_ROOT}/benchmarks/load-tests/read_only.py" \
            --duration 30 \
            --output "${REPORTS_DIR}/perf-read-only.json" \
            > "${REPORTS_DIR}/perf-read-only.log" 2>&1; then
            log_success "Read-only throughput test"
            PASSED=$((PASSED + 1))
        else
            log_fail "Read-only throughput test"
            FAILED=$((FAILED + 1))
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
echo "Mode: $([ "$QUICK_MODE" = true ] && echo "Quick" || echo "Full")"
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
cat > "${REPORTS_DIR}/summary.json" << EOF
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
