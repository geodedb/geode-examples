# `building-social-network` example project

Runnable, real-server-validated examples for the
["Building a Social Network with Geode"](https://codepros.org/blog/building-a-social-network-with-geode/)
blog post (schema, sample data, Python, Go).

## What this proves

This post is the most involved of the four -- a full schema, sample
data, and application code in two languages, plus its own pytest suite
-- and it surfaced by far the most findings, several severe. The schema
and sample-data GQL work exactly as written (including the `Group` node
label the post uses for its `group_id_unique` index -- `Group` is
**not** a reserved word in this GQL dialect). But:

- The post's application code in both languages has **zero
  authentication anywhere** -- a reader who copies either
  `SocialNetwork` class verbatim gets an auth failure on the very first
  database call (the headline finding).
- The post's Go snippets use `$1`/`$2`-style placeholders -- **confirmed
  live that this does NOT work** with real bound parameters (`Error:
  Positional parameter out of range`); `?` is the only working style,
  resolving the `$N`-vs-`?` question this repo has tracked since Task 2
  *against* the plan's original assumption.
- `CREATE UNIQUE INDEX` does **not** actually enforce uniqueness on
  this server, contradicting the post's own claim.
- **Chaining two separate `MATCH` clauses that re-reference an
  already-bound variable silently drops the scoping** and matches
  globally across the whole graph -- confirmed live, and this is the
  exact shape the post's own multi-hop queries use throughout.
- `count(DISTINCT expr)` always returns `null` -- confirmed broken for
  every expression type tried.
- `RETURN entity { .*, ... }` map projection doesn't parse at all; only
  a bare map literal (`RETURN {key: entity.prop, ...}`) works.
- The post's own pytest test's `.as_object` usage returns
  `Dict[str, Value]` (still wrapped), not plain Python types --
  `.raw_value` is the property that actually unwraps to plain types.
- The post's pytest fixture also does `MATCH (n) DETACH DELETE n` as
  teardown, which would wipe the entire shared graph if run as-is.

`FINDINGS.md` documents all of the above with live-captured
reproductions, root causes, and the exact fixes applied in this
project's code.

## Layout

```text
building-social-network/
├── schema.gql            all CREATE (UNIQUE) INDEX statements (post's Steps 1-2)
├── sample_data.gql        post's Step 3 sample data (BEGIN/COMMIT block)
├── python/
│   ├── social_network.py       SocialNetwork class (post's Step 5 Python example)
│   ├── test_social_network.py  post's own pytest suite, adapted for safe cleanup
│   └── requirements.txt
├── go/
│   ├── social_network.go       SocialNetwork struct (post's Step 5 Go example)
│   └── go.mod
├── validate.sh   runs schema + sample data + Python (script + pytest) + Go
├── FINDINGS.md   per-section failure/fix writeup (Task 9's input)
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
`geode-blog-posts` Docker container and exports
`GEODE_HOST`/`GEODE_PORT`/`GEODE_USER`/`GEODE_PASSWORD`), runs
`schema.gql` and `sample_data.gql`, then runs the Python smoke script,
the Python pytest suite, and the Go smoke program in turn, printing
`PASS`/`FAIL` per step and exiting non-zero if any failed.

Each step can also be run individually once the container is up (e.g.
after `source ../_shared/bootstrap.sh` from a `bash` shell -- not
`sh`/`zsh`, see that script's header comment):

```bash
cd python && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python3 social_network.py
pytest test_social_network.py -v

cd ../go && go mod tidy && go run social_network.go
```

### A note on the shared container, rate limiting, and its healthcheck

`validate.sh` and `bootstrap.sh` share one Docker container across every
`blog-posts/*` example project in this repo. The server rate-limits
authentication attempts (successful or not) from a single peer -- see
`../why-quic-matters/FINDINGS.md` and
`../query-optimization-tips/FINDINGS.md` for the earlier occurrences of
this. This project found a materially worse variant: the shared
container's own Docker `HEALTHCHECK` runs every 5 seconds with **no
credentials at all** (a pre-existing bug, see `../_shared/FINDINGS.md`),
and once anything trips the rate limiter, that healthcheck's own
continuous no-auth attempts keep re-tripping it forever -- it does not
recover on its own. `FINDINGS.md` section 11 has the full story and the
runtime-only fix applied to unblock this task (not persisted in
`../_shared/docker-compose.yml`; a future container recreation will
need the same fix reapplied, or `../_shared/docker-compose.yml` updated
to set `GEODE_USERNAME`/`GEODE_PASSWORD` for the healthcheck).
`validate.sh` also paces itself between top-level steps
(`STEP_PACING_SECS`, default 30s) as cheap insurance against the
ordinary (non-perpetual) version of this rate limit.

Nodes accumulate in the shared container across runs (this project's
own `sample_data.gql` and every `smoketest_*`/`go_smoketest_*`/
`pytest_*`-prefixed record from repeated runs), which is expected, not
a failure. `test_social_network.py` additionally generates a fresh
random suffix *per test-process run* (not just a fixed prefix) --
because `CREATE UNIQUE INDEX` doesn't actually enforce uniqueness on
this server (see `FINDINGS.md` section 6), a fixed username would
silently accumulate a duplicate `User` node on every repeated run and
eventually break the pytest suite's exact-count assertions. Nothing in
this project ever runs `MATCH (n) DETACH DELETE n` -- see `FINDINGS.md`
section 5 for why the post's own test fixture doing that is dangerous.

### A note on `bootstrap.sh`'s occasional silent stall

`../_shared/bootstrap.sh`'s "waiting for QUIC transport" step reads the
shared container's accumulated Docker logs on every retry iteration; as
that log has grown across this repo's development, sourcing
`bootstrap.sh` has occasionally stalled/silently returned early without
completing. This is pre-existing, shared-infrastructure flakiness
documented in earlier tasks' reports, not a bug in this project -- if
`source ../_shared/bootstrap.sh` (or `./validate.sh`) appears to hang or
exit without the `[bootstrap] ready: ...` line, just retry it.

## Verification performed

See `FINDINGS.md` for the full writeup. In summary: `schema.gql` and
`sample_data.gql` were run against a live, freshly-bootstrapped
container and confirmed via `SHOW INDEXES` and node-count queries (not
just a clean exit code from `geode query`, which is known to exit 0
even on query-level errors -- see `../query-optimization-tips/FINDINGS.md`).
The Python and Go application code were run for real (not just
type-checked/compiled) against the same container, including the
post's own pytest suite. `validate.sh`'s failure detection was verified
with an intentional-break test (see `FINDINGS.md`) to rule out a false
PASS from the same exit-code-masking bug class caught in earlier tasks.

## Known limitations

- Docker bind-mounts into the CLI's own container are not usable in
  this sandbox environment, so `schema.gql`/`sample_data.gql` are piped
  over stdin (`geode query --format table -`) rather than via
  `--file`. Confirmed to behave identically to `--file` for
  multi-statement input.
