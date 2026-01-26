#!/bin/bash
#
# Geode Benchmark Runner
#
# Runs benchmarks at various profiles: smoke, standard, full, extreme
#
# Usage:
#   ./scripts/run_benchmark.sh [profile] [options]
#
# Profiles:
#   smoke     - Quick validation (1K nodes, 10 connections)
#   standard  - CI/CD benchmark (100K nodes, 100 connections)
#   full      - Release validation (1M nodes, 1K connections)
#   extreme   - Maximum scale (100M nodes, 10K connections)
#
# Options:
#   --no-docker    Use local geode binary instead of docker
#   --skip-data    Skip data generation phase
#   --skip-perf    Skip performance tests
#   --output-dir   Directory for results (default: reports)
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Defaults
PROFILE=${1:-standard}
USE_DOCKER=true
SKIP_DATA=false
SKIP_PERF=false
OUTPUT_DIR="reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Parse arguments
shift || true
while [[ $# -gt 0 ]]; do
    case $1 in
        --no-docker)
            USE_DOCKER=false
            shift
            ;;
        --skip-data)
            SKIP_DATA=true
            shift
            ;;
        --skip-perf)
            SKIP_PERF=true
            shift
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Profile configurations
case $PROFILE in
    smoke)
        NODES=1000
        RELS_PER_NODE=5
        BATCH_SIZE=100
        WORKERS=10
        DURATION=30
        CONNECTIONS=10
        CONN_BATCH=2
        ;;
    standard)
        NODES=100000
        RELS_PER_NODE=5
        BATCH_SIZE=5000
        WORKERS=100
        DURATION=300
        CONNECTIONS=100
        CONN_BATCH=10
        ;;
    full)
        NODES=1000000
        RELS_PER_NODE=5
        BATCH_SIZE=10000
        WORKERS=100
        DURATION=600
        CONNECTIONS=1000
        CONN_BATCH=50
        ;;
    extreme)
        NODES=100000000
        RELS_PER_NODE=10
        BATCH_SIZE=50000
        WORKERS=1000
        DURATION=3600
        CONNECTIONS=10000
        CONN_BATCH=500
        ;;
    *)
        echo -e "${RED}Unknown profile: $PROFILE${NC}"
        echo "Available profiles: smoke, standard, full, extreme"
        exit 1
        ;;
esac

# Header
echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Geode Benchmark Runner${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "Profile:      ${GREEN}$PROFILE${NC}"
echo -e "Nodes:        ${NODES}"
echo -e "Rels/Node:    ${RELS_PER_NODE}"
echo -e "Workers:      ${WORKERS}"
echo -e "Duration:     ${DURATION}s"
echo -e "Connections:  ${CONNECTIONS}"
echo -e "Output:       ${OUTPUT_DIR}"
echo -e "Timestamp:    ${TIMESTAMP}"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Docker flag
DOCKER_FLAG=""
if [ "$USE_DOCKER" = false ]; then
    DOCKER_FLAG="--no-docker"
fi

# Step 1: Generate test data
if [ "$SKIP_DATA" = false ]; then
    echo -e "${YELLOW}Step 1: Generating test data...${NC}"
    python benchmarks/data-generators/scale_test.py \
        --nodes "$NODES" \
        --rels-per-node "$RELS_PER_NODE" \
        --batch-size "$BATCH_SIZE" \
        $DOCKER_FLAG \
        --output "${OUTPUT_DIR}/scale_${PROFILE}_${TIMESTAMP}.json"
    echo -e "${GREEN}Data generation complete.${NC}"
    echo ""
else
    echo -e "${YELLOW}Skipping data generation...${NC}"
fi

# Step 2: Run performance benchmarks
if [ "$SKIP_PERF" = false ]; then
    echo -e "${YELLOW}Step 2: Running read-only throughput benchmark...${NC}"
    python benchmarks/load-tests/read_only.py \
        --workers "$WORKERS" \
        --duration "$DURATION" \
        $DOCKER_FLAG \
        --output "${OUTPUT_DIR}/perf_read_${PROFILE}_${TIMESTAMP}.json"
    echo -e "${GREEN}Read-only benchmark complete.${NC}"
    echo ""

    echo -e "${YELLOW}Step 3: Running read-write mixed workload benchmark...${NC}"
    python benchmarks/load-tests/read_write.py \
        --workers "$WORKERS" \
        --duration "$DURATION" \
        --read-ratio 0.7 \
        $DOCKER_FLAG \
        --output "${OUTPUT_DIR}/perf_rw_${PROFILE}_${TIMESTAMP}.json"
    echo -e "${GREEN}Read-write benchmark complete.${NC}"
    echo ""

    echo -e "${YELLOW}Step 4: Running concurrent connections benchmark...${NC}"
    python benchmarks/load-tests/concurrent_connections.py \
        --target "$CONNECTIONS" \
        --batch-size "$CONN_BATCH" \
        $DOCKER_FLAG \
        --output "${OUTPUT_DIR}/perf_conn_${PROFILE}_${TIMESTAMP}.json"
    echo -e "${GREEN}Concurrent connections benchmark complete.${NC}"
    echo ""
else
    echo -e "${YELLOW}Skipping performance benchmarks...${NC}"
fi

# Summary
echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Benchmark Complete${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo "Results saved to:"
ls -la "${OUTPUT_DIR}"/*_${PROFILE}_${TIMESTAMP}.json 2>/dev/null || echo "  (no files generated)"
echo ""
echo "To view results:"
echo "  cat ${OUTPUT_DIR}/perf_read_${PROFILE}_${TIMESTAMP}.json | python -m json.tool"
echo ""
