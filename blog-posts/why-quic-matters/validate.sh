#!/usr/bin/env bash
# Runs all five "Why QUIC Matters for Graph Databases" example scripts
# (four Python, one Go) against one freshly-bootstrapped Geode container
# and prints a PASS/FAIL summary. See README.md for prerequisites.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

# Must be sourced from bash, not sh/zsh -- see ../_shared/bootstrap.sh.
source ../_shared/bootstrap.sh

fail=0
run() {
  local name="$1"; shift
  echo "=== $name ==="
  if "$@" 2>&1 | grep -v 'DebugAllocator\|\.zig:\|libc_start\|additional stack'; then
    echo "PASS: $name"
  else
    echo "FAIL: $name"
    fail=1
  fi
}

run "python:dashboard_concurrency" bash -c '
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
  # IMPORTANT: capture the real exit code explicitly and exit with it as
  # the *last* statement. deactivate (a shell function that always exits
  # 0) must never be the last command here -- if it were, its own success
  # would become the exit status of this whole bash -c block, silently
  # masking a real failure in the Python script. See
  # introducing-geode/task-2-report.md fix-pass for the false PASS this
  # exact bug class caused there; verified NOT repeated here (see
  # README.md "Verification performed").
  python3 dashboard_concurrency.py
  ec=$?
  deactivate
  exit $ec
'

run "python:connection_timing" bash -c '
  cd python
  source .venv/bin/activate
  python3 connection_timing.py
  ec=$?
  deactivate
  exit $ec
'

run "python:stream_large_result" bash -c '
  cd python
  source .venv/bin/activate
  python3 stream_large_result.py
  ec=$?
  deactivate
  exit $ec
'

run "python:monitoring" bash -c '
  cd python
  source .venv/bin/activate
  python3 monitoring.py
  ec=$?
  deactivate
  exit $ec
'

run "go:transaction_pipelining" bash -c '
  cd go
  go mod tidy >/dev/null
  go run transaction_pipelining.go
'

echo "==================================="
if [ "$fail" -eq 0 ]; then
  echo "ALL PASS"
else
  echo "ONE OR MORE EXAMPLES FAILED -- see output above and FINDINGS.md"
fi

exit $fail
