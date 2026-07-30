# `why-quic-matters` example project

Runnable, real-server-validated examples for the
["Why QUIC Matters for Graph Databases"](https://codepros.org/blog/why-quic-matters-for-graph-databases/)
blog post (Python + Go).

Every file here validates one code example from the post:

| File | Post section |
|------|--------------|
| `python/dashboard_concurrency.py` | "Stream Multiplexing" -- parallel queries on one connection |
| `python/connection_timing.py` | "0-RTT Connection Resumption" -- `measure_connection_time` |
| `python/stream_large_result.py` | "Efficient Result Streaming" |
| `python/monitoring.py` | "Monitoring" -- `client.get_connection_stats()` |
| `go/transaction_pipelining.go` | "Transaction Pipelining" |

## What this proves

The post's code snippets were written before being validated against a
running server. All five examples needed at least a fix to run for real;
one (`monitoring.py`) turned out to validate a feature that **does not
exist** in the real client library at all. `FINDINGS.md` documents, per
example: the original post snippet, the exact failure running it as-is,
what had to change (with real captured output/error text), and the
corrected snippet -- written so it can be applied to the blog post
directly without touching a container.

## Layout

```text
why-quic-matters/
├── python/
│   ├── dashboard_concurrency.py
│   ├── connection_timing.py
│   ├── stream_large_result.py
│   ├── monitoring.py
│   └── requirements.txt
├── go/
│   ├── transaction_pipelining.go
│   ├── go.mod
│   └── go.sum
├── validate.sh   runs all five against one freshly-bootstrapped container
├── FINDINGS.md   per-example failure/fix writeup (Task 7's input)
└── README.md     this file
```

## Prerequisites

- Docker (for the shared Geode container -- see `../_shared/bootstrap.sh`)
- Go 1.24+
- Python 3.9+

## Running

```bash
./validate.sh
```

This sources `../_shared/bootstrap.sh` (starts/reuses the shared
`geode-blog-posts` Docker container and exports `GEODE_HOST`/`GEODE_PORT`/
`GEODE_USER`/`GEODE_PASSWORD`), then runs each example in turn, printing
`PASS`/`FAIL` per example and exiting non-zero if any failed.

Each example can also be run individually once the container is up (e.g.
after `source ../_shared/bootstrap.sh` from a `bash` shell -- not `sh`/`zsh`,
see that script's header comment):

```bash
cd python && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python3 dashboard_concurrency.py
python3 connection_timing.py
python3 stream_large_result.py
python3 monitoring.py

cd ../go && go mod tidy && go run transaction_pipelining.go
```

### A note on the shared container and rate limiting

`validate.sh` and `bootstrap.sh` share one Docker container across every
`blog-posts/*` example project in this repo. The server rate-limits
authentication attempts (successful or not) from a single peer. Running
`bootstrap.sh` repeatedly in quick succession during manual debugging (each
invocation runs its own auth sanity-check) can trip this limit; if you see
`Error: Too many failed authentication attempts. Please try again later.`,
wait 60-90 seconds and retry. `validate.sh` itself sources `bootstrap.sh`
exactly once per run and should not trigger this in normal use. See
`introducing-geode/FINDINGS.md`'s Rust section for the full story.

Nodes accumulate in the shared container across runs (each example adds
its own), so `dashboard_concurrency.py`'s printed counts grow with
repeated runs -- that's expected, not a failure.

### A note on `bootstrap.sh`'s occasional silent stall

`../_shared/bootstrap.sh`'s "waiting for QUIC transport" step reads the
shared container's accumulated Docker logs on every retry iteration; as
that log has grown across Tasks 2-3's development (well over 1000 lines),
sourcing `bootstrap.sh` has occasionally stalled/silently returned early
without completing. This is pre-existing, shared-infrastructure flakiness
documented in `introducing-geode/task-2-report.md`'s fix pass, not a bug
in this project -- if `source ../_shared/bootstrap.sh` (or `./validate.sh`)
appears to hang or exit without the `[bootstrap] ready: ...` line, just
retry it.

## Known limitation

`monitoring.py` demonstrates that `client.get_connection_stats()` -- the
post's entire "Monitoring" section -- **does not exist** in the real
`geode-client` Python package (confirmed via live `AttributeError` and
`dir()` introspection of both `Client` and `Connection`, cross-checked
against the client's own README API Reference table). See `FINDINGS.md`
section 4 for the full detail and recommended fix for the blog post.
