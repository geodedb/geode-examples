#!/usr/bin/env bash
# These are standalone demonstration programs with mock clients. Compile or
# execute each example without starting a database they never connect to.
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
mkdir -p "$root/reports"
case "${1:-}" in
  go)
    cd "$root/clients/go"
    go test -vet=off -p=2 ./... 2>&1 | tee "$root/reports/go-tests.log"
    ;;
  python)
    cd "$root/clients/python"
    python3 -m compileall -q examples 2>&1 | tee "$root/reports/python-tests.log"
    ;;
  rust)
    cd "$root/clients/rust"
    cargo test --examples -j 2 2>&1 | tee "$root/reports/rust-tests.log"
    ;;
  nodejs)
    cd "$root/clients/nodejs"
    npm run all 2>&1 | tee "$root/reports/nodejs-tests.log"
    ;;
  zig)
    cd "$root/clients/zig"
    zig build test -j2 --summary all 2>&1 | tee "$root/reports/zig-tests.log"
    ;;
  *) echo 'Expected client: go, python, rust, nodejs, zig' >&2; exit 64 ;;
esac
