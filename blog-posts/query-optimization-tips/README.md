# `query-optimization-tips` example project

Runnable, real-server-validated examples for the
["10 Query Optimization Tips for Geode"](https://codepros.org/blog/10-query-optimization-tips-for-geode/)
blog post.

Every file under `tips/` and `bonus/` contains exactly the **"Solution"**
GQL block from the corresponding tip in the post (the "Problem"/slow
blocks are illustrative only and are not run here -- several are
intentionally pathological, e.g. Tip 3's unbounded `[:KNOWS*]`
traversal, and could hang against seeded data).

## What this proves

Unlike the other three example projects in this repo, this post has no
client-library code at all -- every example is raw GQL run through
`geode query --file`/stdin, plus `EXPLAIN`/`PROFILE`. Running every
"Solution" block against a live, freshly-seeded container surfaced real
gaps between what the post describes and what the server actually does:
`UNWIND` does not parse at all, `WITH ... LIMIT ... CREATE` silently
creates nothing, an implicit-grouping `RETURN` the post itself documents
as valid sometimes isn't, and three of the four vector-similarity
functions the "Use Vector Indexes" bonus tip depends on
(`distance`/`similarity`/`knn`) always return `null` -- only `cosine()`
actually computes a value. `FINDINGS.md` documents each one: the
original post snippet, the exact failure running it as-is, what had to
change, and the corrected snippet. The full real `EXPLAIN`/`PROFILE`
output for Tip 10 -- compared against the post's illustrative
plan-node-name example -- is also in `FINDINGS.md`.

## Layout

```text
query-optimization-tips/
├── seed.gql        500 Person, 50 Company, 20 Document nodes + WORKS_AT/KNOWS/WORKS_WITH edges
├── tips/            01_indexes.gql .. 10_profile.gql (one file per numbered tip)
├── bonus/           compound_index.gql, vector_index.gql, batch_ops.gql, params.gql, denormalize.gql
├── validate.sh      runs seed.gql + all 15 tip/bonus files against one freshly-bootstrapped container
├── FINDINGS.md       per-file failure/fix writeup + Tip 10's real EXPLAIN/PROFILE output (Task 8's input)
└── README.md         this file
```

## Prerequisites

- Docker
- The shared bootstrap script at `../_shared/bootstrap.sh` (starts/reuses
  the `geode-blog-posts` container and exports `GEODE_HOST`,
  `GEODE_PORT`, `GEODE_USER`, `GEODE_PASSWORD`)

## Running it yourself

```bash
cd blog-posts/query-optimization-tips
./validate.sh
```

`validate.sh` sources `../_shared/bootstrap.sh` (must be run from bash,
not zsh/sh), seeds a fresh copy of the graph, then runs every tip/bonus
file with `geode query --format table -` piped from each `.gql` file,
pacing each invocation to stay under the server's connection-rate
authentication limiter (see FINDINGS.md).

## A note on pacing

This server's authentication path rate-limits repeated connections from
the same peer IP -- confirmed live, repeatedly, while developing this
project: firing off more than a handful of `docker run ... geode
query ...` invocations within about a minute reliably trips
"Authentication rate limit exceeded" / "Too many failed authentication
attempts. Please try again later.", even with the correct password every
time. `validate.sh` paces itself (15s between queries by default,
override with `QUERY_PACING_SECS`); if you're driving `geode query`
directly against the shared container, expect the same limiter if you
fire off queries in a tight loop.

## Verification performed

- `./validate.sh` run clean against a freshly-seeded container (all 17
  steps -- reset + seed + 15 tip/bonus files -- PASS).
- Intentional-break test: temporarily broke one query file to confirm
  `validate.sh` genuinely reports a non-zero exit and `FAIL:` on a real
  error (not just echoing "PASS" regardless of outcome), then reverted.
