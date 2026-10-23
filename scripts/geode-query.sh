#!/usr/bin/env bash
# Pass queries as arguments, never interpolate GQL into shell source.
set -euo pipefail
exec docker compose exec -T geode sh -c \
  'exec geode query --server localhost:3141 --ca-cert /data/server.crt -U geode -P "$GEODE_ADMIN_PASSWORD" "$@"' \
  geode-query "$@"
