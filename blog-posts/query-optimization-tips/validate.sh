#!/usr/bin/env bash
# Runs seed.gql plus all 15 "10 Query Optimization Tips for Geode"
# tip/bonus GQL files against one freshly-bootstrapped Geode container and
# prints a PASS/FAIL summary. See README.md for prerequisites.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

# Must be sourced from bash, not sh/zsh -- see ../_shared/bootstrap.sh.
source ../_shared/bootstrap.sh

# This server's authentication path rate-limits repeated connections from
# the same peer IP (confirmed live: rapid-fire `docker run ... geode
# query` invocations reliably trip "Authentication rate limit exceeded"
# / "Too many failed authentication attempts" within well under a
# minute, even with a correct password every time -- see FINDINGS.md).
# Pace every query invocation below to stay under that limit.
QUERY_PACING_SECS="${QUERY_PACING_SECS:-15}"

# Runs one .gql file's statements against the shared container over
# stdin. IMPORTANT, two layers of exit-code hazard here, both confirmed
# live and both would otherwise produce a false PASS:
#
# 1. The real `docker run` exit code is captured into $ec *before*
#    piping through grep for the human-readable leak-noise filter --
#    grep becomes the last command in the pipe, and under `pipefail`
#    its own (unrelated) exit code would otherwise replace docker run's
#    real one. See the introducing-geode and why-quic-matters
#    FINDINGS.md for the same bug class (a trailing cleanup/filter
#    command masking the real exit code) biting earlier tasks in this
#    plan.
#
# 2. The `geode` CLI itself exits 0 even when the *query* errors --
#    confirmed live: `geode query "MATCHX (n) RETURN n"` prints `Error:
#    parse error` to stdout/stderr but the process exits 0. Only
#    connection/auth-level failures (e.g. `Error: Authentication
#    failed`) produce a non-zero exit. This was caught by this
#    project's own intentional-break test (see README.md "Verification
#    performed") -- the first version of this function relied on exit
#    code alone and reported a false PASS on a deliberately broken
#    query. The fix: also grep the CLI's own output for its
#    line-anchored `Error:` prefix as a second, independent failure
#    signal. (Anchored to line-start so it can't false-positive on
#    unrelated lowercase `error_bytes`/`error_abs_pct` fields inside
#    tips/10_profile.gql's legitimate PROFILE JSON output.) See
#    FINDINGS.md #10.
run_query() {
  local file="$1"
  shift
  local raw filtered
  raw="$(docker run --rm -i --network container:geode-blog-posts \
    -e GEODE_ALLOW_INSECURE_TLS=1 geodedb/geode:latest \
    query -U "$GEODE_USER" --password "$GEODE_PASSWORD" \
    --server "127.0.0.1:${GEODE_PORT}" --insecure-tls-skip-verify \
    --format table "$@" - < "$file" 2>&1)"
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
  if run_query "$@"; then
    echo "PASS: $name"
  else
    echo "FAIL: $name"
    fail=1
  fi
  sleep "$QUERY_PACING_SECS"
}

# Reset step: makes re-running this script against the same shared
# container idempotent. Wipes all nodes/relationships from any prior run
# and drops the specific indexes the tip/bonus files below create (`IF
# EXISTS` -- confirmed supported live -- makes this a no-op on a fresh
# container). Without this, a second run fails on "index already
# exists" for tips/01 and bonus/compound_index and bonus/vector_index.
RESET_FILE="$(mktemp --suffix=.gql)"
trap 'rm -f "$RESET_FILE"' EXIT
cat > "$RESET_FILE" <<'GQL'
MATCH (n) DETACH DELETE n;
DROP INDEX IF EXISTS person_email;
DROP INDEX IF EXISTS person_country_age;
DROP INDEX IF EXISTS doc_embedding_idx;
GQL
run "reset (wipe data + drop this project's indexes)" "$RESET_FILE"

run "seed.gql" seed.gql

run "tips/01_indexes.gql" tips/01_indexes.gql
run "tips/02_filter_early.gql" tips/02_filter_early.gql
run "tips/03_limit_paths.gql" tips/03_limit_paths.gql
run "tips/04_use_limit.gql" tips/04_use_limit.gql
run "tips/05_optimize_aggregations.gql" tips/05_optimize_aggregations.gql
run "tips/06_with_pipeline.gql" tips/06_with_pipeline.gql
run "tips/07_avoid_cartesian.gql" tips/07_avoid_cartesian.gql
run "tips/08_relationship_types.gql" tips/08_relationship_types.gql
run "tips/09_exists.gql" tips/09_exists.gql
run "tips/10_profile.gql" tips/10_profile.gql

run "bonus/compound_index.gql" bonus/compound_index.gql
run "bonus/vector_index.gql" bonus/vector_index.gql --param query_vector '[0.1,0.2,0.3,0.4]'
run "bonus/batch_ops.gql" bonus/batch_ops.gql
run "bonus/params.gql" bonus/params.gql --param name '"Person1"'
run "bonus/denormalize.gql" bonus/denormalize.gql

echo "==================================="
if [ "$fail" -eq 0 ]; then
  echo "ALL PASS"
else
  echo "ONE OR MORE FILES FAILED -- see output above and FINDINGS.md"
fi

exit $fail
