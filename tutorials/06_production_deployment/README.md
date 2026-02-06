# Tutorial 6: Production Deployment

This tutorial covers deploying Geode in production environments, including
Docker, Kubernetes, and security hardening.

**CANARY: REQ=REQ-TUTORIAL-006; FEATURE="ProductionDeployment"; ASPECT=Documentation; STATUS=COMPLETE**

## Prerequisites

- Docker and Docker Compose
- Kubernetes cluster (for K8s deployment)
- Helm 3.x
- TLS certificates
- Basic understanding of deployment concepts

## Part 1: Docker Production Deployment

### Single-Node Docker Deployment

```yaml
# docker-compose.production.yml
version: '3.8'

services:
  geode:
    image: geodedb/geode:0.1.4
    restart: always
    ports:
      - "3141:3141"
      - "9090:9090"  # Metrics
    volumes:
      - geode-data:/var/lib/geode
      - geode-wal:/var/lib/geode/wal
      - ./certs:/certs:ro
    environment:
      - GEODE_CONFIG=/etc/geode/production.yaml
    healthcheck:
      test: ["CMD", "geode", "health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G

volumes:
  geode-data:
  geode-wal:
```

### Launch Production Docker

```bash
# Create certificate directory
mkdir -p certs
# Copy your TLS certificates
cp /path/to/server.crt certs/
cp /path/to/server.key certs/

# Start production deployment
docker compose -f docker-compose.production.yml up -d

# Check logs
docker compose -f docker-compose.production.yml logs -f geode
```

## Part 2: Kubernetes Deployment

### Basic Kubernetes Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: geode
  labels:
    app: geode
spec:
  replicas: 1
  selector:
    matchLabels:
      app: geode
  template:
    metadata:
      labels:
        app: geode
    spec:
      containers:
      - name: geode
        image: geodedb/geode:0.1.4
        ports:
        - containerPort: 3141
          name: geode
        - containerPort: 9090
          name: metrics
        resources:
          requests:
            cpu: "2"
            memory: "4Gi"
          limits:
            cpu: "4"
            memory: "8Gi"
        volumeMounts:
        - name: data
          mountPath: /var/lib/geode
        - name: config
          mountPath: /etc/geode
        - name: certs
          mountPath: /certs
          readOnly: true
        livenessProbe:
          exec:
            command: ["geode", "health"]
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          exec:
            command: ["geode", "health", "--ready"]
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: geode-data
      - name: config
        configMap:
          name: geode-config
      - name: certs
        secret:
          secretName: geode-tls
```

### Service Configuration

```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: geode
  labels:
    app: geode
spec:
  type: ClusterIP
  ports:
  - port: 3141
    targetPort: 3141
    name: geode
  - port: 9090
    targetPort: 9090
    name: metrics
  selector:
    app: geode
```

### Apply Kubernetes Resources

```bash
# Create namespace
kubectl create namespace geode

# Create TLS secret
kubectl create secret tls geode-tls \
  --cert=certs/server.crt \
  --key=certs/server.key \
  -n geode

# Create config
kubectl create configmap geode-config \
  --from-file=production.yaml \
  -n geode

# Apply deployment
kubectl apply -f k8s/ -n geode

# Check status
kubectl get pods -n geode
kubectl logs -f deployment/geode -n geode
```

## Part 3: Helm Chart Deployment

### Using the Geode Helm Chart

```bash
# Add Geode Helm repository (example)
helm repo add geode https://charts.geodedb.com
helm repo update

# Or use local chart
helm install geode ./helm/geode \
  --namespace geode \
  --create-namespace \
  -f values-production.yaml
```

### Production Values

```yaml
# values-production.yaml
replicaCount: 3

image:
  repository: geodedb/geode
  tag: "0.1.4"
  pullPolicy: IfNotPresent

resources:
  requests:
    cpu: "2"
    memory: "4Gi"
  limits:
    cpu: "4"
    memory: "8Gi"

persistence:
  enabled: true
  size: 500Gi
  storageClass: fast-ssd

config:
  server:
    max_connections: 10000
  storage:
    page_cache_size: "4GB"
  security:
    tde_enabled: true
    tls_min_version: "1.3"

monitoring:
  enabled: true
  serviceMonitor:
    enabled: true
```

## Part 4: Security Hardening

### TLS Configuration

Always use TLS 1.3 with strong cipher suites:

```yaml
# security-hardened.yaml
security:
  tls_enabled: true
  tls_cert_file: "/certs/server.crt"
  tls_key_file: "/certs/server.key"
  tls_min_version: "1.3"

  # Only TLS 1.3 cipher suites
  tls_cipher_suites:
    - TLS_AES_256_GCM_SHA384
    - TLS_AES_128_GCM_SHA256
    - TLS_CHACHA20_POLY1305_SHA256
```

### Enable TDE (Transparent Data Encryption)

```yaml
security:
  tde_enabled: true
  tde_algorithm: "AES-256-GCM"
  tde_key_source: "vault"
  tde_vault_addr: "https://vault.internal:8200"
  tde_vault_path: "secret/geode/encryption-key"
```

### Enable Authentication and MFA

```yaml
security:
  auth_enabled: true

  password_policy:
    min_length: 12
    require_uppercase: true
    require_lowercase: true
    require_numbers: true
    require_special: true
    max_age_days: 90
    history_count: 5
    lockout_threshold: 5
    lockout_duration_minutes: 30

  mfa_enabled: true
  mfa_type: "totp"
```

### Enable Audit Logging

```yaml
security:
  audit_enabled: true
  audit_log_path: "/var/log/geode/audit.log"
  audit_rotation: "daily"
  audit_retention: "90d"
  audit_events:
    - authentication
    - authorization
    - data_access
    - schema_changes
    - admin_operations
```

## Part 5: High Availability

### Raft Cluster Configuration

```yaml
# raft-cluster.yaml
replication:
  mode: "raft"
  cluster_name: "geode-prod"

  peers:
    - "geode-0.geode.svc:3142"
    - "geode-1.geode.svc:3142"
    - "geode-2.geode.svc:3142"

  raft:
    election_timeout: "1s"
    heartbeat_interval: "100ms"
    snapshot_threshold: 10000
```

### StatefulSet for HA

```yaml
# k8s/statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: geode
spec:
  serviceName: geode
  replicas: 3
  selector:
    matchLabels:
      app: geode
  template:
    metadata:
      labels:
        app: geode
    spec:
      containers:
      - name: geode
        image: geodedb/geode:0.1.4
        env:
        - name: POD_NAME
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        - name: GEODE_RAFT_PEER_ID
          value: "$(POD_NAME)"
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: fast-ssd
      resources:
        requests:
          storage: 500Gi
```

## Part 6: Monitoring

### Prometheus Integration

Geode exposes Prometheus metrics on port 9090:

```yaml
# prometheus-servicemonitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: geode
  labels:
    app: geode
spec:
  selector:
    matchLabels:
      app: geode
  endpoints:
  - port: metrics
    interval: 15s
    path: /metrics
```

### Key Metrics to Monitor

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `geode_connections_active` | Active connections | > 9000 |
| `geode_query_latency_p99` | P99 query latency | > 100ms |
| `geode_storage_bytes` | Storage usage | > 80% |
| `geode_raft_leader` | Raft leader status | Changed |
| `geode_cache_hit_ratio` | Page cache hit rate | < 90% |

### Grafana Dashboard

Import the Geode dashboard from `monitoring/dashboards/geode-overview.json`.

## Part 7: Backup and Recovery

### Enable Point-in-Time Recovery

```yaml
storage:
  wal_enabled: true
  wal_dir: "/var/lib/geode/wal"
  wal_sync_interval: "100ms"

backup:
  enabled: true
  schedule: "0 2 * * *"  # Daily at 2 AM
  retention: 30
  destination: "s3://backups/geode/"
```

### Manual Backup

```bash
# Trigger backup via CLI
geode admin backup create --name "pre-upgrade-$(date +%Y%m%d)"

# List backups
geode admin backup list

# Restore from backup
geode admin backup restore --name "pre-upgrade-20240115"
```

## Part 8: Production Checklist

### Pre-Deployment

- [ ] TLS certificates configured
- [ ] TDE encryption keys in secure storage
- [ ] Authentication enabled
- [ ] MFA enabled for admin accounts
- [ ] Audit logging configured
- [ ] Resource limits set
- [ ] Persistent storage provisioned
- [ ] Backup schedule configured

### Post-Deployment

- [ ] Health checks passing
- [ ] Metrics being collected
- [ ] Alerts configured
- [ ] Backups verified
- [ ] Disaster recovery tested
- [ ] Load testing completed
- [ ] Security scan passed

### Ongoing Operations

- [ ] Monitor key metrics
- [ ] Review audit logs
- [ ] Rotate TLS certificates
- [ ] Apply security updates
- [ ] Test backup restoration
- [ ] Review capacity planning

## Troubleshooting

### Common Issues

**Pod not starting:**
```bash
kubectl describe pod geode-0 -n geode
kubectl logs geode-0 -n geode
```

**Connection refused:**
```bash
# Check service
kubectl get svc geode -n geode
# Check endpoints
kubectl get endpoints geode -n geode
```

**Raft cluster issues:**
```bash
# Check cluster status
geode admin cluster status
# View Raft logs
kubectl logs geode-0 -n geode | grep -i raft
```

## Summary

You've learned:
- Docker production deployment
- Kubernetes deployment with Helm
- Security hardening configuration
- High availability with Raft
- Monitoring and alerting
- Backup and recovery

For more information, see the [Geode Documentation](https://docs.geodedb.com).
