#!/usr/bin/env bash
# Starts the shared Geode container (if not already running), waits for it
# to become reachable, and exports connection env vars for every other
# script in blog-posts/*/validate.sh to consume via:
#   source ../_shared/bootstrap.sh
#
# Auth approach (see _shared/FINDINGS.md section 2 for the full story):
# the server's own default flow -- read the auto-generated password from
# /data/.geode_admin_password, then run
# `ALTER USER geode SET PASSWORD '...'` as its error message instructs --
# changes the password successfully but does NOT clear the server's
# password_reset_required flag, so every future query is permanently
# rejected with "Password reset required" even with the correct new
# password. That self-service recovery path is a dead end in this image.
#
# Instead, this script generates a fresh admin password and seeds it via
# the GEODE_ADMIN_PASSWORD environment variable *before* the container's
# first boot. That bypasses the auto-generated-password/forced-reset flow
# entirely -- confirmed working end-to-end against a live container.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTAINER_NAME="geode-blog-posts"
PW_FILE="/tmp/.geode-blog-posts-admin-password"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
  echo "[bootstrap] starting $CONTAINER_NAME..."

  # Confirmed password policy for this server (found by iterating on real
  # ALTER USER ... SET PASSWORD validation error messages -- see
  # FINDINGS.md section 2 for the full derivation):
  #   - minimum 20 characters
  #   - at least one uppercase letter
  #   - at least one lowercase letter
  #   - must be a passphrase of at least 3 space-separated words
  # No digit or special-character requirement was found. Note: this
  # policy is enforced on ALTER USER SET PASSWORD calls, but NOT enforced
  # on GEODE_ADMIN_PASSWORD seeding at first boot (a weak env-seeded value
  # is accepted) -- we still generate a policy-satisfying value here as
  # good practice for the example projects that consume it.
  NEW_PW="Correct Horse Battery Staple ${RANDOM}${RANDOM}"
  echo -n "$NEW_PW" > "$PW_FILE"
  chmod 600 "$PW_FILE"

  GEODE_ADMIN_PASSWORD="$NEW_PW" docker compose -f "$SCRIPT_DIR/docker-compose.yml" up -d
fi

echo "[bootstrap] waiting for container to be running..."
for i in $(seq 1 30); do
  status="$(docker inspect -f '{{.State.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo "missing")"
  [ "$status" = "running" ] && break
  sleep 1
done
if [ "$status" != "running" ]; then
  echo "[bootstrap] FATAL: container never reached 'running' (status=$status)" >&2
  docker logs "$CONTAINER_NAME" 2>&1 | tail -50 >&2
  exit 1
fi

# The image's HEALTHCHECK is known-broken (see FINDINGS.md) even with
# GEODE_ALLOW_INSECURE_TLS=1 set — confirm the *real* readiness signal
# instead: the QUIC listener log line.
#
# `docker logs ... | grep -q ...` is unsafe here: under `pipefail`, once
# `grep -q` finds its match it exits immediately and closes its end of the
# pipe, and `docker logs` — mid-write against a container log that keeps
# growing across repeated calls in this loop — can be signaled (SIGPIPE)
# before it finishes, turning "found it" into a spurious pipeline failure.
# Two tasks downstream hit this as an intermittent non-zero exit as the
# shared container's log grew. Redirecting to a file first removes the
# live pipe entirely: `docker logs` always runs to completion, and
# `grep -q FILE` reads a static, fully-written snapshot.
echo "[bootstrap] waiting for QUIC transport to report 'listening'..."
LOG_SNAPSHOT="$(mktemp)"
for i in $(seq 1 30); do
  docker logs "$CONTAINER_NAME" >"$LOG_SNAPSHOT" 2>&1 || true
  if grep -q '"status":"listening"' "$LOG_SNAPSHOT"; then
    break
  fi
  sleep 1
done
rm -f "$LOG_SNAPSHOT"

# Resolve the container's IP directly rather than trusting hostname
# resolution over the QUIC/UDP path (see FINDINGS.md).
GEODE_HOST="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$CONTAINER_NAME" | head -1)"
GEODE_PORT=3141

if [ ! -f "$PW_FILE" ]; then
  echo "[bootstrap] FATAL: $CONTAINER_NAME is running but $PW_FILE is missing -- can't recover the admin password it was seeded with. Remove the container (docker rm -f $CONTAINER_NAME) and re-run this script to get a fresh one." >&2
  exit 1
fi

export GEODE_HOST GEODE_PORT
export GEODE_USER="geode"
export GEODE_PASSWORD="$(cat "$PW_FILE")"
export GEODE_ALLOW_INSECURE_TLS=1
export GEODE_DSN_QUIC="quic://${GEODE_HOST}:${GEODE_PORT}?insecure_tls_skip_verify=true"

# Sanity-check the credentials actually work before declaring success.
# (Leak-report noise on stderr from the CLI's DebugAllocator is expected
# and harmless here -- see FINDINGS.md section 3 -- so it's filtered.)
health_output="$(docker run --rm --network container:"$CONTAINER_NAME" \
  -e GEODE_ALLOW_INSECURE_TLS=1 geodedb/geode:latest \
  query -U "$GEODE_USER" --password "$GEODE_PASSWORD" --server "127.0.0.1:${GEODE_PORT}" \
  --insecure-tls-skip-verify --format json "RETURN 1 AS health" 2>&1 \
  | grep -v 'DebugAllocator\|\.zig:\|libc_start\|additional stack')"

if ! echo "$health_output" | grep -q '"health"'; then
  echo "[bootstrap] FATAL: sanity-check query with the bootstrapped credentials failed: $health_output" >&2
  exit 1
fi

echo "[bootstrap] ready: host=$GEODE_HOST port=$GEODE_PORT user=$GEODE_USER"
