# `introducing-geode` example project

Runnable, real-server-validated examples for the
["Introducing Geode: A Modern Graph Database for the QUIC Era"](https://codepros.org/blog/introducing-geode-a-modern-graph-database-for-the-quic-era/)
blog post.

Every language directory here performs the same two operations from the
post's Getting Started section:

```gql
CREATE (:Person {name: "Alice", age: 30})
MATCH (p:Person) RETURN p
```

plus that language's own "Native Language Support" snippet from the post
(adapted where the post's snippet didn't match the real client API -- see
`FINDINGS.md`).

## What this proves

The post's code snippets were written before being validated against a
running server. Every snippet needed at least a DSN/auth fix to actually
work; Node.js also hit a real client-library decode bug. `FINDINGS.md`
documents, per language: the original post snippet, the exact failure
running it as-is, what had to change, and the corrected snippet -- written
so it can be applied to the blog post directly without touching a
container.

## Layout

```text
introducing-geode/
├── go/          main.go, go.mod
├── python/      getting_started.py, requirements.txt
├── rust/        Cargo.toml, src/main.rs
├── nodejs/      package.json, index.mjs
├── zig/         build.zig, build.zig.zon, src/main.zig
├── validate.sh  runs all five against one freshly-bootstrapped container
├── FINDINGS.md  per-language failure/fix writeup (Task 6's input)
└── README.md    this file
```

## Prerequisites

- Docker (for the shared Geode container -- see `../_shared/bootstrap.sh`)
- Go 1.24+
- Python 3.9+
- Rust (a toolchain matching the `geode-client` crate's MSRV, 1.85+; the
  crate's own transitive deps may require newer -- 1.97+ was used to
  validate this project)
- Node.js 20+
- Zig 0.16.0+ (the `geode-client-zig` package's `minimum_zig_version`; note
  this is newer than the blog post's own "Zig 0.16.0+ to build the server
  from source" requirement, so a single toolchain covers both)

## Running

```bash
./validate.sh
```

This sources `../_shared/bootstrap.sh` (starts/reuses the shared
`geode-blog-posts` Docker container and exports `GEODE_HOST`/`GEODE_PORT`/
`GEODE_USER`/`GEODE_PASSWORD`), then runs each language's example in turn,
printing `PASS`/`FAIL` per language and exiting non-zero if any failed.

Each language can also be run individually once the container is up (e.g.
after `source ../_shared/bootstrap.sh` from a `bash` shell -- not `sh`/`zsh`,
see that script's header comment):

```bash
cd go && go run main.go
cd python && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && python3 getting_started.py
cd rust && cargo run
cd nodejs && npm install && node index.mjs
cd zig && zig build run
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
`FINDINGS.md`'s Rust section for the full story.

Person nodes accumulate in the shared container across runs (each language
adds its own), so the printed count in each language's `OK: N Person
node(s) returned` line grows with repeated runs -- that's expected, not a
failure.

## Known limitation

Node.js's `MATCH (p:Person) RETURN p` (returning the whole graph node, as
literally shown in the post) hits a confirmed decode bug in
`@geodedb/client@1.1.0` for node IDs larger than
`Number.MAX_SAFE_INTEGER` (every node ID on this server). `nodejs/index.mjs`
works around it by querying `p.name`/`p.age` instead of the whole node --
see `FINDINGS.md` section 4 for the full repro and root cause.
