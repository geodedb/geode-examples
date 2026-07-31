#!/usr/bin/env bash
# Runs schema.gql + sample_data.gql, then the Python and Go
# "SocialNetwork" application examples (including the Python pytest
# suite), against one freshly-bootstrapped Geode container and prints a
# PASS/FAIL summary. See README.md for prerequisites.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

# Must be sourced from bash, not sh/zsh -- see ../_shared/bootstrap.sh.
source ../_shared/bootstrap.sh

# This server's authentication path rate-limits repeated connections
# from the same peer IP -- confirmed live and independently by three
# prior tasks in this repo (see ../why-quic-matters/FINDINGS.md and
# ../query-optimization-tips/FINDINGS.md). This project found a much
# worse variant: the shared container's own Docker HEALTHCHECK runs
# every 5s with no credentials (a pre-existing, separately documented
# bug -- see ../_shared/FINDINGS.md), and once ANYTHING pushes the
# limiter into its tripped state, the healthcheck's own continuous
# no-auth attempts every 5s keep re-tripping it forever -- it never
# recovers on its own. See FINDINGS.md for the full story and the fix
# applied to unblock this task's own validation run. Pacing between
# steps here is cheap insurance against the ordinary (non-perpetual)
# version of this rate limit.
STEP_PACING_SECS="${STEP_PACING_SECS:-30}"

# Runs one .gql file's statements against the shared container over
# stdin. Two exit-code hazards apply here, both confirmed live in prior
# tasks and both would otherwise produce a false PASS -- see
# query-optimization-tips/validate.sh for the full explanation:
#   1. `set -uo pipefail` (pipefail set) makes the pipeline's exit
#      status the last non-zero command scanned right-to-left, so the
#      leak-noise `grep -v` filter does not mask a real failure.
#   2. The `geode` CLI itself exits 0 even when the *query* errors --
#      only connection/auth-level failures produce a non-zero exit. So
#      also grep the CLI's own output for a line-anchored `Error:` as a
#      second, independent failure signal.
run_query() {
  local file="$1"
  local raw filtered
  raw="$(docker run --rm -i --network container:geode-blog-posts \
    -e GEODE_ALLOW_INSECURE_TLS=1 geodedb/geode:latest \
    query -U "$GEODE_USER" --password "$GEODE_PASSWORD" \
    --server "127.0.0.1:${GEODE_PORT}" --insecure-tls-skip-verify \
    --format table - < "$file" 2>&1)"
  local ec=$?
  filtered="$(echo "$raw" | grep -v 'DebugAllocator\|\.zig:\|libc_start\|additional stack')"
  echo "$filtered"
  if [ "$ec" -ne 0 ]; then
    return 1
  fi
  if echo "$filtered" | grep -q '^Error:'; then
    return 1
  fi
  return 0
}

fail=0
run() {
  local name="$1"; shift
  echo "=== $name ==="
  if "$@"; then
    echo "PASS: $name"
  else
    echo "FAIL: $name"
    fail=1
  fi
  sleep "$STEP_PACING_SECS"
}

# Idempotency: re-running this script against an already-bootstrapped
# container fails schema.gql with "Error: Duplicate index name" (the
# CLI still exits 0 -- see run_query's own comment above -- so
# run_query's output-text check correctly reports this as FAIL, which
# is technically accurate but not useful noise on a second run). Drop
# just this project's own indexes first, IF EXISTS, so validate.sh is
# safely re-runnable. This does NOT touch any node/relationship data
# (see README.md/FINDINGS.md for why this project never wipes data).
RESET_FILE="$(mktemp --suffix=.gql)"
trap 'rm -f "$RESET_FILE"' EXIT
{
  grep -E '^CREATE' schema.gql | grep -oE 'INDEX [a-zA-Z_][a-zA-Z0-9_]*' | awk '{print "DROP INDEX IF EXISTS " $2 ";"}'
} > "$RESET_FILE"
run "reset (drop this project's indexes, IF EXISTS)" run_query "$RESET_FILE"

run "schema.gql" run_query schema.gql
run "sample_data.gql" run_query sample_data.gql

run "python:social_network (smoke script)" bash -c '
  cd python
  if [ ! -d .venv ]; then
    python3 -m venv .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
    pip install -q -r requirements.txt
  else
    # shellcheck disable=SC1091
    source .venv/bin/activate
  fi
  # Capture the real exit code explicitly and exit with it as the *last*
  # statement -- deactivate (a shell function that always exits 0) must
  # never be the last command here, or its own success would mask a
  # real failure in the Python script. See why-quic-matters/validate.sh
  # for the same discipline.
  python3 social_network.py 2>&1 | grep -v "DebugAllocator\|\.zig:\|libc_start\|additional stack"
  ec=${PIPESTATUS[0]}
  deactivate
  exit $ec
'

run "python:pytest" bash -c '
  cd python
  source .venv/bin/activate
  pytest test_social_network.py -v 2>&1 | grep -v "DebugAllocator\|\.zig:\|libc_start\|additional stack"
  ec=${PIPESTATUS[0]}
  deactivate
  exit $ec
'

run "go:social_network" bash -c '
  cd go
  go mod tidy >/dev/null
  go run social_network.go 2>&1 | grep -v "DebugAllocator\|\.zig:\|libc_start\|additional stack"
  exit ${PIPESTATUS[0]}
'

echo "==================================="
if [ "$fail" -eq 0 ]; then
  echo "ALL PASS"
else
  echo "ONE OR MORE STEPS FAILED -- see output above and FINDINGS.md"
fi

exit $fail
