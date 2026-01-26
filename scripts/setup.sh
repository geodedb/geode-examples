#!/bin/bash
# setup.sh - Environment setup for Geode Examples
#
# Usage: ./scripts/setup.sh [--with-monitoring] [--with-kafka]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Parse arguments
WITH_MONITORING=false
WITH_KAFKA=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --with-monitoring)
            WITH_MONITORING=true
            shift
            ;;
        --with-kafka)
            WITH_KAFKA=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

cd "$PROJECT_ROOT"

log_info "Setting up Geode Examples environment..."

# Check prerequisites
log_info "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    log_error "Docker is required but not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    log_error "Docker Compose is required but not installed."
    exit 1
fi

# Create required directories
log_info "Creating directories..."
mkdir -p certs reports benchmarks/results

# Generate self-signed certificates for development
if [ ! -f certs/server.crt ]; then
    log_info "Generating self-signed TLS certificates..."
    openssl req -x509 -newkey rsa:4096 \
        -keyout certs/server.key \
        -out certs/server.crt \
        -days 365 \
        -nodes \
        -subj "/CN=localhost/O=Geode Development"

    # Generate TDE key
    openssl rand -base64 32 > certs/tde.key
    chmod 600 certs/tde.key certs/server.key

    log_info "Certificates generated in certs/"
fi

# Build Docker images
log_info "Building Docker images..."

# Check if geode source exists
GEODE_DIR="${PROJECT_ROOT}/../geode"
if [ ! -d "$GEODE_DIR" ]; then
    log_error "Geode source not found at $GEODE_DIR"
    log_error "Please clone the geode repository first."
    exit 1
fi

# Build compose profiles
PROFILES=""
if [ "$WITH_MONITORING" = true ]; then
    PROFILES="$PROFILES --profile monitoring"
fi

if [ "$WITH_KAFKA" = true ]; then
    PROFILES="$PROFILES --profile cdc"
fi

# Build and start services
log_info "Building Geode server image..."
docker compose build geode

log_info "Starting Geode server..."
docker compose up -d geode $PROFILES

# Wait for Geode to be healthy
log_info "Waiting for Geode to be healthy..."
max_attempts=30
attempt=1
while [ $attempt -le $max_attempts ]; do
    if docker compose exec -T geode geode shell -c "RETURN 1" &> /dev/null; then
        log_info "Geode is healthy!"
        break
    fi
    echo -n "."
    sleep 2
    attempt=$((attempt + 1))
done

if [ $attempt -gt $max_attempts ]; then
    log_error "Geode failed to become healthy"
    docker compose logs geode
    exit 1
fi

# Display connection info
echo ""
log_info "Setup complete!"
echo ""
echo "Geode server is running at:"
echo "  - QUIC endpoint: localhost:3141"
echo "  - Metrics: http://localhost:9090/metrics"
echo ""
echo "Connect with shell:"
echo "  docker compose exec geode geode shell"
echo ""
echo "Run tests:"
echo "  make test"
echo ""
echo "Run benchmarks:"
echo "  make benchmark"
echo ""

if [ "$WITH_MONITORING" = true ]; then
    echo "Monitoring:"
    echo "  - Prometheus: http://localhost:9091"
    echo "  - Grafana: http://localhost:3000 (admin/geode)"
    echo ""
fi
