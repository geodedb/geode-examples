#!/bin/bash
#
# Geode Production Server Setup Script
#
# Sets up a bare metal or VM server for large-scale Geode testing.
# Optimizes system settings for high-performance graph database workloads.
#
# Usage:
#   sudo ./scripts/setup_production_server.sh
#
# Requirements:
#   - Ubuntu 22.04+ or Debian 12+
#   - Root access
#   - NVMe SSD storage recommended
#

set -e

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

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   log_error "This script must be run as root (use sudo)"
   exit 1
fi

log_info "Starting Geode production server setup..."

# =============================================================================
# System Requirements Check
# =============================================================================

log_info "Checking system requirements..."

# Check CPU cores
CPU_CORES=$(nproc)
if [[ $CPU_CORES -lt 8 ]]; then
    log_warn "Only $CPU_CORES CPU cores detected. Recommended: 32+ for extreme scale testing."
fi
log_info "CPU cores: $CPU_CORES"

# Check memory
TOTAL_MEM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_MEM_GB=$((TOTAL_MEM_KB / 1024 / 1024))
if [[ $TOTAL_MEM_GB -lt 32 ]]; then
    log_warn "Only ${TOTAL_MEM_GB}GB RAM detected. Recommended: 256GB+ for extreme scale testing."
fi
log_info "Total memory: ${TOTAL_MEM_GB}GB"

# Check disk space
DISK_SPACE_GB=$(df -BG / | awk 'NR==2 {print $4}' | tr -d 'G')
if [[ $DISK_SPACE_GB -lt 100 ]]; then
    log_warn "Only ${DISK_SPACE_GB}GB disk space available. Recommended: 2TB+ for extreme scale testing."
fi
log_info "Available disk space: ${DISK_SPACE_GB}GB"

# =============================================================================
# System Tuning
# =============================================================================

log_info "Configuring system limits..."

# Configure file descriptor limits
cat > /etc/security/limits.d/99-geode.conf << 'EOF'
# Geode database server limits
* soft nofile 1048576
* hard nofile 1048576
* soft nproc 65536
* hard nproc 65536
* soft memlock unlimited
* hard memlock unlimited
root soft nofile 1048576
root hard nofile 1048576
EOF

log_info "Configuring kernel parameters..."

# Configure kernel parameters
cat > /etc/sysctl.d/99-geode.conf << 'EOF'
# Network tuning for high connection counts
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_keepalive_time = 300
net.ipv4.tcp_keepalive_probes = 5
net.ipv4.tcp_keepalive_intvl = 15
net.ipv4.tcp_tw_reuse = 1
net.ipv4.ip_local_port_range = 1024 65535

# Memory tuning for large datasets
vm.swappiness = 1
vm.dirty_ratio = 40
vm.dirty_background_ratio = 10
vm.overcommit_memory = 1
vm.max_map_count = 262144

# File system tuning
fs.file-max = 2097152
fs.inotify.max_user_watches = 524288
fs.aio-max-nr = 1048576

# Disable transparent huge pages for consistent performance
# (configure separately via systemd service)
EOF

# Apply sysctl settings
sysctl -p /etc/sysctl.d/99-geode.conf

# =============================================================================
# Disable Transparent Huge Pages
# =============================================================================

log_info "Disabling transparent huge pages..."

cat > /etc/systemd/system/disable-thp.service << 'EOF'
[Unit]
Description=Disable Transparent Huge Pages (THP)
DefaultDependencies=no
After=sysinit.target local-fs.target
Before=basic.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'echo never > /sys/kernel/mm/transparent_hugepage/enabled'
ExecStart=/bin/sh -c 'echo never > /sys/kernel/mm/transparent_hugepage/defrag'

[Install]
WantedBy=basic.target
EOF

systemctl daemon-reload
systemctl enable disable-thp
systemctl start disable-thp

# =============================================================================
# Create Geode User and Directories
# =============================================================================

log_info "Creating geode user and directories..."

# Create geode user if it doesn't exist
if ! id "geode" &>/dev/null; then
    useradd -r -m -d /var/lib/geode -s /bin/bash geode
fi

# Create directories
mkdir -p /var/lib/geode/data
mkdir -p /var/lib/geode/wal
mkdir -p /var/log/geode
mkdir -p /etc/geode
mkdir -p /opt/geode/bin

# Set permissions
chown -R geode:geode /var/lib/geode
chown -R geode:geode /var/log/geode
chown -R geode:geode /etc/geode
chown -R geode:geode /opt/geode

# =============================================================================
# Create Geode Configuration
# =============================================================================

log_info "Creating Geode configuration..."

# Calculate recommended page cache (50% of RAM, max 128GB)
RECOMMENDED_CACHE_GB=$((TOTAL_MEM_GB / 2))
if [[ $RECOMMENDED_CACHE_GB -gt 128 ]]; then
    RECOMMENDED_CACHE_GB=128
fi
if [[ $RECOMMENDED_CACHE_GB -lt 2 ]]; then
    RECOMMENDED_CACHE_GB=2
fi

cat > /etc/geode/geode.yaml << EOF
# Geode Production Configuration
# Generated by setup_production_server.sh

server:
  listen: "0.0.0.0:3141"
  metrics_listen: "0.0.0.0:9090"
  max_connections: 10000
  connection_timeout: "60s"
  idle_timeout: "10m"

storage:
  data_dir: "/var/lib/geode/data"
  wal_dir: "/var/lib/geode/wal"
  page_size: 16384
  page_cache_size: "${RECOMMENDED_CACHE_GB}GB"
  wal_buffer_size: "128MB"
  wal_sync_interval: "50ms"
  compression: "zstd"

security:
  tde_enabled: false
  tls_enabled: false
  auth_enabled: false

logging:
  level: "info"
  format: "json"
  file: "/var/log/geode/geode.log"
EOF

chown geode:geode /etc/geode/geode.yaml

# =============================================================================
# Create Systemd Service
# =============================================================================

log_info "Creating systemd service..."

cat > /etc/systemd/system/geode.service << 'EOF'
[Unit]
Description=Geode Graph Database Server
Documentation=https://geodedb.com/docs
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=geode
Group=geode
WorkingDirectory=/var/lib/geode

ExecStart=/opt/geode/bin/geode serve --config /etc/geode/geode.yaml
ExecReload=/bin/kill -HUP $MAINPID

Restart=always
RestartSec=5

# Resource limits
LimitNOFILE=1048576
LimitNPROC=65536
LimitMEMLOCK=infinity
LimitCORE=infinity

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/var/lib/geode /var/log/geode

# Environment
Environment="GEODE_DATA_DIR=/var/lib/geode/data"

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

# =============================================================================
# Install Dependencies
# =============================================================================

log_info "Installing dependencies..."

apt-get update
apt-get install -y \
    curl \
    wget \
    ca-certificates \
    libssl3 \
    htop \
    iotop \
    sysstat \
    dstat \
    python3 \
    python3-pip \
    python3-venv

# =============================================================================
# Create Helper Scripts
# =============================================================================

log_info "Creating helper scripts..."

# Server start script
cat > /opt/geode/bin/geode-start << 'EOF'
#!/bin/bash
systemctl start geode
echo "Geode server started. Check status with: systemctl status geode"
EOF
chmod +x /opt/geode/bin/geode-start

# Server stop script
cat > /opt/geode/bin/geode-stop << 'EOF'
#!/bin/bash
systemctl stop geode
echo "Geode server stopped."
EOF
chmod +x /opt/geode/bin/geode-stop

# Status check script
cat > /opt/geode/bin/geode-status << 'EOF'
#!/bin/bash
echo "=== Geode Server Status ==="
systemctl status geode --no-pager
echo ""
echo "=== Resource Usage ==="
if pgrep -x geode > /dev/null; then
    ps aux | grep -E "^USER|geode" | grep -v grep
    echo ""
    echo "=== Open Files ==="
    ls /proc/$(pgrep -x geode)/fd 2>/dev/null | wc -l
    echo " file descriptors open"
    echo ""
    echo "=== Memory Map Count ==="
    wc -l < /proc/$(pgrep -x geode)/maps 2>/dev/null || echo "N/A"
fi
EOF
chmod +x /opt/geode/bin/geode-status

# Benchmark helper script
cat > /opt/geode/bin/geode-benchmark << 'EOF'
#!/bin/bash
# Quick benchmark helper
PROFILE=${1:-standard}
WORKERS=${2:-10}
DURATION=${3:-60}

echo "Running $PROFILE benchmark..."
echo "  Workers: $WORKERS"
echo "  Duration: ${DURATION}s"

cd /opt/geode/geode-examples 2>/dev/null || {
    echo "geode-examples not found. Clone it to /opt/geode/geode-examples"
    exit 1
}

python3 benchmarks/load-tests/read_only.py \
    --workers $WORKERS \
    --duration $DURATION \
    --no-docker \
    --output reports/bench_${PROFILE}_$(date +%Y%m%d_%H%M%S).json
EOF
chmod +x /opt/geode/bin/geode-benchmark

# Add to PATH
echo 'export PATH=$PATH:/opt/geode/bin' >> /etc/profile.d/geode.sh

# =============================================================================
# Summary
# =============================================================================

echo ""
log_info "=========================================="
log_info "Geode production server setup complete!"
log_info "=========================================="
echo ""
echo "System configuration:"
echo "  - CPU cores: $CPU_CORES"
echo "  - Memory: ${TOTAL_MEM_GB}GB"
echo "  - Page cache: ${RECOMMENDED_CACHE_GB}GB"
echo "  - Max connections: 10,000"
echo "  - Max file descriptors: 1,048,576"
echo ""
echo "Directories created:"
echo "  - Data: /var/lib/geode/data"
echo "  - WAL:  /var/lib/geode/wal"
echo "  - Logs: /var/log/geode"
echo "  - Config: /etc/geode/geode.yaml"
echo ""
echo "Next steps:"
echo "  1. Copy geode binary to /opt/geode/bin/geode"
echo "  2. Start server: systemctl start geode"
echo "  3. Check status: systemctl status geode"
echo "  4. View logs: journalctl -u geode -f"
echo ""
echo "For benchmarking:"
echo "  1. Clone geode-examples to /opt/geode/geode-examples"
echo "  2. Run: /opt/geode/bin/geode-benchmark [profile] [workers] [duration]"
echo ""
log_info "Reboot recommended to apply all system settings."
