#!/usr/bin/env bash
# Runs all five "Introducing Geode" example projects (Go, Python, Rust,
# Node.js, Zig) against one freshly-bootstrapped Geode container and prints
# a PASS/FAIL summary. See README.md for prerequisites.
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

run "go" bash -c '
  cd go
  go mod tidy >/dev/null
  go run main.go
'

run "python" bash -c '
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
  # IMPORTANT: capture the exit code of getting_started.py explicitly and
  # exit with it as the *last* statement. deactivate (a shell function that
  # always exits 0) must never be the last command here -- if it were, its
  # own success would become the exit status of this whole bash -c block,
  # silently masking a real failure in getting_started.py. See the fix-pass
  # section of task-2-report.md for the false PASS this caused.
  python3 getting_started.py
  ec=$?
  deactivate
  exit $ec
'

run "rust" bash -c '
  cd rust
  cargo run --quiet
'

run "nodejs" bash -c '
  cd nodejs
  if [ ! -d node_modules ]; then
    npm install --silent
  fi
  node index.mjs
'

run "zig" bash -c '
  cd zig
  zig build run
'

echo "==================================="
if [ "$fail" -eq 0 ]; then
  echo "ALL PASS"
else
  echo "ONE OR MORE LANGUAGES FAILED -- see output above and FINDINGS.md"
fi

exit $fail
