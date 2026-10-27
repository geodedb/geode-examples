#!/usr/bin/env bash
# Pass queries as arguments, never interpolate GQL into shell source.
set -euo pipefail
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
response=$(mktemp)
batch=
cleanup() {
  rm -f "$response"
  if [[ -n "$batch" ]]; then rm -f "$batch"; fi
}
trap cleanup EXIT
run_query() {
  docker compose exec -T geode sh -c \
    'exec geode query --server localhost:3141 --ca-cert /data/server.crt -U geode -P "$GEODE_ADMIN_PASSWORD" "$@"' \
    geode-query "$@" | tee "$response"
}
if [[ "${1:-}" == --file ]]; then
  # Batch mode retains one connection but sends each statement separately.
  # EXPLAIN/PROFILE and explicit rollback require separate query messages;
  # the CLI's --file mode combines them into unsupported multi-statement queries.
  batch=$(mktemp)
  python3 "$script_dir/gql-batch.py" "${2:?query file required}" > "$batch"
  shift 2
  run_query --batch "$@" < "$batch"
else
  run_query "$@"
fi
python3 "$script_dir/check-geode-response.py" "$response"
