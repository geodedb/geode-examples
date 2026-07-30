# FINDINGS: `query-optimization-tips` example project

Real, live-server findings from validating every "Solution" GQL block in
the "10 Query Optimization Tips for Geode" blog post against a running
`geodedb/geode:latest` (v0.8.4) container. Environment: shared
`geode-blog-posts` container from `blog-posts/_shared/bootstrap.sh`,
`geode query --format table -` (stdin) run from inside a
`--network container:geode-blog-posts` sidecar container (volume mounts
into the CLI container are not usable in this sandbox -- bind-mount
sources outside the environment silently resolve to an empty directory
inside the container, so every file is piped over stdin instead; `geode
query -` behaves identically to `--file` for multi-statement input,
confirmed by testing both: only the *last* statement's result is printed
in `--format table`, same as `--file`).

This document is written to be Task 8's entire input for correcting the
blog post itself.

---

## 0. Slug correction

The plan text and task brief both refer to this post's URL as
`https://codepros.org/blog/query-optimization-tips-for-geode/`. The
site's actual permalink is derived from the post's **title**, not its
filename (`permalinks: blog: /blog/:slug/` in
`config/_default/config.yaml`), and the built site confirms the real
path is `public/blog/10-query-optimization-tips-for-geode/index.html`
with `<title>10 Query Optimization Tips for Geode | CodePros</title>`.
The correct URL is:

```text
https://codepros.org/blog/10-query-optimization-tips-for-geode/
```

`README.md` in this project links to the corrected slug.

---

## 1. `UNWIND` does not parse at all

**Where it matters**: the brief's suggested `seed.gql` (all four
statements use `UNWIND ... AS i CREATE (...)`), and the "Batch
Operations" bonus tip's Solution block
(`BEGIN UNWIND range(0, 999) AS i CREATE (:Person {id: i}) COMMIT`).

**Confirmed live** (reconfirmed here; first found in the
`why-quic-matters` example project, see its `FINDINGS.md`):

```text
> UNWIND [1,2,3] AS i RETURN i;
Error: parse error
```

Every variant tried failed identically: list literal, `range()`,
lowercase `unwind`, with/without trailing `;`. `UNWIND` is documented in
this repo's own `geode:syntax`/`geode:examples` skill references but is
not implemented (or not reachable via this CLI/wire-protocol path) on
this server build.

**Fix applied**:

- `seed.gql`: rewritten as single multi-pattern `CREATE` statements (one
  `CREATE` with N comma-separated node patterns, same round-trip
  economics `UNWIND` would have given).
- `bonus/batch_ops.gql`: rewritten the same way inside `BEGIN`/`COMMIT`.
  Original vs. fixed:

  ```gql
  -- Post's Solution (does not parse):
  BEGIN
    UNWIND range(0, 999) AS i
    CREATE (:Person {id: i});
  COMMIT

  -- Fixed (live-validated):
  BEGIN
    CREATE (:Person {id: 0}), (:Person {id: 1}), ..., (:Person {id: 999});
  COMMIT;
  ```

**Task 8 recommendation**: either drop `UNWIND` from every GQL example in
this post (replace with multi-pattern `CREATE`), or add an explicit note
that `UNWIND` is not yet implemented -- as written, the post's Batch
Operations solution does not run.

---

## 2. `WITH ... LIMIT ... CREATE` silently creates nothing

**Where it matters**: the brief's suggested seed statement for `KNOWS`
edges: `... WITH p1, p2 LIMIT 800 CREATE (p1)-[:KNOWS]->(p2)`.

**Confirmed live** with a minimal repro (3 nodes):

```text
> CREATE (:T {id:1}),(:T {id:2}),(:T {id:3});
> MATCH (p1:T),(p2:T) WHERE p1.id<p2.id WITH p1,p2 LIMIT 2 CREATE (p1)-[:K]->(p2) RETURN count(*);
+----------+
| ?column? |
+----------+
| 1        |
+----------+
(1 row)
> MATCH (a:T)-[:K]->(b:T) RETURN a.id, b.id;
(0 rows)
```

The query reports success and even returns a row from `count(*)`, but
zero relationships are actually created -- `WITH ... CREATE` (whether or
not `LIMIT` sits between them) does not execute the `CREATE`. This is
silent: no error, no exception, just a no-op that looks like it worked.

**Fix applied**: `seed.gql`'s `KNOWS`/`WORKS_WITH` edge counts are bounded
via a `WHERE`-clause condition instead of `WITH ... LIMIT`.

**Task 8 recommendation**: this is a genuine server bug, not a
documentation issue -- flag it to the Geode team directly (a `WITH ...
CREATE` pattern that silently drops the write is a correctness hazard
far beyond this one blog post). If the post ever grows a `WITH ...
LIMIT ... CREATE` example, it needs an explicit warning until this is
fixed upstream.

---

## 3. Rate limiting on repeated authenticated connections

Not specific to this post's GQL, but material to reproducing any of the
above: this server's authentication path rate-limits repeated
connections from the same peer IP. Firing off more than roughly half a
dozen `docker run ... geode query ...` invocations within about a
minute reliably trips:

```text
Error: Too many failed authentication attempts. Please try again later.
```

(logged server-side as `WARN geode.server Authentication rate limit
exceeded peer_ip=127.0.0.1`) -- even though every attempt used the
correct password. `validate.sh` paces itself at `QUERY_PACING_SECS=15`
between queries to stay under this.

---

## 4. Implicit grouping (as documented in the post) does not work

**Where it matters**: Tip 5's Solution
(`RETURN p.department, count(p)`) and, transitively, Tip 2's Solution
(`RETURN p.name, count(friend)`) -- both rely on the post's own note
under Tip 5:

> GQL uses **implicit grouping**: any non-aggregated expression in the
> `RETURN` clause automatically becomes a grouping key. There is no
> separate `GROUP BY` clause -- `RETURN p.department, count(p)` groups by
> `p.department` on its own.

**Confirmed live, both the two-MATCH Tip 2 query and the minimal
single-MATCH Tip 5 query fail identically**:

```text
> MATCH (p:Person)-[:WORKS_AT]->(c:Company)
  RETURN p.department, count(p);
Error: grouping error: non-aggregated expression not in GROUP BY
```

Adding an explicit `GROUP BY` clause fixes it and returns the expected
result:

```text
> MATCH (p:Person)-[:WORKS_AT]->(c:Company)
  RETURN p.department, count(p)
  GROUP BY p.department;
+-------------+-------+
| department  | count |
+-------------+-------+
| Engineering | 120   |
| Sales       | 125   |
| Marketing   | 120   |
| Support     | 125   |
+-------------+-------+
(4 rows)
```

**Fix applied**: added an explicit `GROUP BY` clause to `tips/02_filter_early.gql`
and `tips/05_optimize_aggregations.gql`.

**Task 8 recommendation**: this is a direct, must-fix inaccuracy in the
post's own explanatory text under Tip 5 -- either the "implicit
grouping" note is wrong for this server build and needs to be corrected
to say `GROUP BY` is required, or (if implicit grouping is intended
future/spec behavior not yet implemented) the note needs a caveat and
every `RETURN <key>, count(...)` example in the post needs an explicit
`GROUP BY` added. As published, the post's own two aggregation examples
do not run.

## 5. `length(path)` evaluated through `WITH` silently returns 0

**Where it matters**: Tip 6's Solution
(`WITH p, friend, length(path) AS path_length WHERE path_length > 2
RETURN p.name, path_length`) -- the entire point of this tip is
"compute the expensive expression once via WITH instead of
re-evaluating it".

**Confirmed live**, isolated to exactly this: `length(path)` evaluated
directly in a top-level `RETURN` (no `WITH` involved) returns correct
values --

```text
> MATCH path = (p:Person)-[:KNOWS*1..3]-(friend)
  RETURN length(path) AS L LIMIT 10;
+---+
| L |
+---+
| 1 |
| 1 |
| 2 |
| 2 |
| 3 |
| 3 |
...
```

-- but the *same* `length(path)` expression, carried through a `WITH`
projection, always evaluates to `0`:

```text
> MATCH path = (p:Person)-[:KNOWS*1..3]-(friend)
  WITH p, friend, length(path) AS L
  RETURN p.name, L LIMIT 5;
+-----------+---+
| name      | L |
+-----------+---+
| Person394 | 0 |
| Person394 | 0 |
| Person394 | 0 |
| Person394 | 0 |
| Person394 | 0 |
+-----------+---+
(5 rows)
```

Because `L` is always `0`, Tip 6's `WHERE path_length > 2` filters out
every row -- the query "succeeds" (no error) but silently returns 0
rows, even though real length-3 paths exist in the underlying data (as
the un-WITH'd version above proves).

**Fix applied**: none -- `tips/06_with_pipeline.gql` keeps the post's
exact Solution GQL verbatim. Unlike the parse-error cases above (#1),
this query runs without error and just as the post specifies, so
"fixing" it (e.g. by not routing `length(path)` through `WITH`) would
misrepresent what the post's own recommended code actually does when
run for real -- readers deserve to see the real (silently wrong)
behavior. `validate.sh` treats this file as PASS (exit 0, no error) even
though its result set is empty; that gap between "ran without error"
and "produced the intended result" is exactly why this section of
FINDINGS.md exists.

**Task 8 recommendation**: this is a genuine server bug in `WITH`
projections that carry a path-derived expression, not a documentation
issue -- it directly undermines Tip 6's core claim ("computes once with
WITH" silently computes a wrong constant instead). Flag to the Geode
team; until fixed, the post should not recommend routing `length(path)`
through `WITH`, or should add a caveat that this pattern currently
returns 0 on this server build.

## 6. `EXISTS(<pattern>)` does not parse; `EXISTS { <pattern> }` does

**Where it matters**: Tip 9's Solution
(`WHERE EXISTS((p)-[:KNOWS]->())`).

**Confirmed live**:

```text
> MATCH (p:Person) WHERE EXISTS((p)-[:KNOWS]->()) RETURN p;
Error: parse error
```

The curly-brace subquery form parses and runs correctly:

```text
> MATCH (p:Person) WHERE EXISTS { (p)-[:KNOWS]->() } RETURN p LIMIT 5;
+----------+
| p        |
+----------+
| (Person) |
...
(5 rows)
```

**Fix applied**: `tips/09_exists.gql` uses `EXISTS { (p)-[:KNOWS]->() }`.

**Task 8 recommendation**: this server implements the newer ISO/IEC
39075:2024 `EXISTS { <pattern> }` subquery syntax, not the
parenthesized-pattern shorthand the post shows. Update Tip 9's Solution
block to the curly-brace form.

---

## 7. Tip 10: real `EXPLAIN`/`PROFILE` output vs. the post's illustrative example (the key evidence)

The post shows `EXPLAIN` and `PROFILE` for:

```gql
MATCH (p:Person)-[:KNOWS*2..3]-(friend)
WHERE p.age > 30
RETURN friend.name
```

as simple ASCII tables:

```text
EXPLAIN -> | plan | with rows: EXPLAIN / MATCH / NodeScan / Filter / VarLengthExpand / RETURN / Project
PROFILE -> | metric | value | with rows_returned=1000, columns=1, execution_time_ms=187
```

**Real output, captured verbatim, run against this project's seeded
data** (`geode query --format table -` was used for both -- the server
ignores `--format table` for `EXPLAIN`/`PROFILE` specifically and always
returns raw JSON regardless of the requested format):

**`EXPLAIN`** (query plan, not executed):

```json
{"schema":"planned_explain.v1","ops":[{"idx":0,"kind":"LabelScan","est_rows":0,"cost":0},{"idx":1,"kind":"VarLengthExpand","est_rows":0,"cost":0},{"idx":2,"kind":"Filter","est_rows":0,"cost":0},{"idx":3,"kind":"Project","est_rows":0,"cost":0},{"idx":4,"kind":"LegacyExecute","est_rows":0,"cost":0}],"totals":{"est_rows":0,"cost":0},"profile_version":2,"properties":{"ordered":false}}
```

**`PROFILE`** (executed, with real stats -- 500 Person / 50 Company / 20
Document nodes, 1473 relationships seeded at the time this ran):

```json
{"profile_version":2,"ops":[{"op":"LabelScan","phase":"SCAN","id":0,"op_index":0,"input_rows":0,"rows":0,"time_ns":0,"cpu_time_ns":0,"bytes_out":0,"bytes_alloc":0,"estimate_bytes":0,"estimate_vs_actual":0,"percent_peak":0,"percent_net":0,"cumulative_time_ns":0,"freed_bytes":0,"net_after_op":0,"error_bytes":0,"error_abs_pct":0},{"op":"VarLengthExpand","phase":"EXPAND","id":0,"op_index":1,"input_rows":0,"rows":0,"time_ns":0,"cpu_time_ns":0,"bytes_out":0,"bytes_alloc":0,"estimate_bytes":0,"estimate_vs_actual":0,"percent_peak":0,"percent_net":0,"cumulative_time_ns":0,"freed_bytes":0,"net_after_op":0,"error_bytes":0,"error_abs_pct":0},{"op":"Filter","phase":"FILTER","id":0,"op_index":2,"input_rows":0,"rows":0,"time_ns":0,"cpu_time_ns":0,"bytes_out":0,"bytes_alloc":0,"estimate_bytes":0,"estimate_vs_actual":0,"percent_peak":0,"percent_net":0,"cumulative_time_ns":0,"freed_bytes":0,"net_after_op":0,"error_bytes":0,"error_abs_pct":0},{"op":"Project","phase":"PROJECT","id":0,"op_index":3,"input_rows":0,"rows":0,"time_ns":0,"cpu_time_ns":0,"bytes_out":0,"bytes_alloc":0,"estimate_bytes":0,"estimate_vs_actual":0,"percent_peak":0,"percent_net":0,"cumulative_time_ns":0,"freed_bytes":0,"net_after_op":0,"error_bytes":0,"error_abs_pct":0},{"op":"LegacyExecute","phase":"EXECUTE","id":0,"op_index":4,"input_rows":1512,"rows":1512,"time_ns":6010758,"cpu_time_ns":6010758,"bytes_out":0,"bytes_alloc":0,"estimate_bytes":0,"estimate_vs_actual":0,"percent_peak":0,"percent_net":0,"cumulative_time_ns":6010758,"freed_bytes":0,"net_after_op":0,"error_bytes":0,"error_abs_pct":0}],"peak_contributors":[],"totals":{"time_ns":6010758,"peak_bytes":0},"total_time_ns":6010758,"spills":{"sort_spills":0,"distinct_spills":0,"union_spills":0},"memory":{"net_bytes":0,"peak_bytes":0,"total_alloc_bytes":0},"hashagg_spills":0,"committed_txns":0,"graph_store_nodes":573,"graph_store_edges":1473,"graph_store_dirty":false,"flagger_findings":["I:PropertyOrderingEnabled","U:NullsFirstPolicy","GB03:DoubleSolidusComment"]}
```

**Comparison against the post's illustrative example**:

| Aspect | Post shows | Real server output |
|---|---|---|
| Output format | Simple 2-column ASCII table (`\| plan \|` / `\| metric \| value \|`) | Raw structured JSON (`profile_version`, per-op cost/timing/byte stats, `flagger_findings`, etc.) -- returned even when `--format table` is explicitly requested |
| Scan operator name | `NodeScan` | `LabelScan` |
| Operator present in post | `NodeScan`, `Filter`, `VarLengthExpand`, `Project` (4 ops) | `LabelScan`, `VarLengthExpand`, `Filter`, `Project`, **`LegacyExecute`** (5 ops) -- the post never mentions a `LegacyExecute` op at all |
| Operator order | `NodeScan` -> `Filter` -> `VarLengthExpand` (under `MATCH`) -> `Project` (under `RETURN`) | `LabelScan` -> `VarLengthExpand` -> `Filter` -> `Project` -> `LegacyExecute` -- Filter comes *after* VarLengthExpand, not before |
| `PROFILE` top-level metrics | `rows_returned`, `columns`, `execution_time_ms` (3 flat fields) | No such top-level fields at all -- instead per-op `input_rows`/`rows`/`time_ns`/`cpu_time_ns`/byte-level stats, plus query-level `total_time_ns`, `graph_store_nodes`, `graph_store_edges`, `spills`, `memory`, `hashagg_spills`, `committed_txns` |
| Example numeric result | `execution_time_ms: 187` | `total_time_ns: 6010758` (~6ms) -- not directly comparable (different dataset/hardware), but the *shape* of the number (a top-level millisecond count) does not exist in the real output at all |

**Task 8 recommendation**: the post's `EXPLAIN`/`PROFILE` section needs a
substantial rewrite, not a spot-fix -- it is not just that `NodeScan`
should say `LabelScan`. The whole *output format* is wrong: this server
returns structured JSON with a materially different schema (extra ops,
different order, per-op cost/timing breakdown, no top-level
`rows_returned`/`execution_time_ms` fields), not the simple two-column
ASCII table the post illustrates. Recommend replacing the illustrative
tables with a real captured JSON sample (e.g. the one above, or a
freshly captured one against the post's own final dataset) and updating
the "How to spot it" guidance to reference the real field names
(`op`/`kind`, `time_ns`, `rows`) instead of the imagined
`rows_returned`/`execution_time_ms`.

---

## 8. Distributed `EXPLAIN`/`PROFILE` rejection claim: NOT VALIDATED

Tip 10's note claims: "Geode rejects `.explain`/`.profile` requests
against a distributed query with a structured error."

**NOT VALIDATED (requires multi-node cluster, out of scope for this
project).** This project's environment is a single shared
`geode-blog-posts` container (see `blog-posts/_shared/bootstrap.sh`) --
there is no sharded/federated cluster available to stand up and no
distributed query to run `EXPLAIN`/`PROFILE` against. This claim was
neither confirmed nor refuted; it is explicitly out of scope for a
single-container example project. If Task 8 or a future task needs this
validated, it requires a real multi-node Geode deployment.

---

## 9. Vector-similarity functions: three of four always return `null`

**Where it matters**: the "Use Vector Indexes for Similarity Search"
bonus tip's Solution
(`WHERE distance(d.embedding, $query_vector, 'l2') < 0.5` and
`knn(d.embedding, $query_vector, 10)`), and the post's own text
referencing `distance`, `similarity`, `knn` as "the full function
reference."

**Confirmed live**, with clean, unambiguous literal-only inputs (no
property access, no index involved -- ruling out data/index issues):

```text
> RETURN distance([0.0,0.0], [3.0,4.0], "l2");        -> null
> RETURN distance([0.0,0.0], [3.0,4.0], "euclidean");  -> null
> RETURN distance([0.0,0.0], [3.0,4.0]);               -> null  (2-arg form)
> RETURN euclidean([0.0,0.0], [3.0,4.0]);              -> null
> RETURN similarity([1.0,0.0], [1.0,0.0], "cosine");   -> null
> RETURN similarity([1.0,0.0], [1.0,0.0]);             -> null  (2-arg form)
> RETURN cosine([1.0,0.0], [1.0,0.0]);                 -> 1.000000  (correct!)
```

`cosine()` is the *only* one of the four vector functions mentioned in
this post (`distance`, `similarity`, `knn`, plus `cosine`/`euclidean`
from the CLI's own `geode:syntax` reference) that actually computes a
value. `distance()`, `similarity()`, `euclidean()`, and `knn()` all
return `null` unconditionally, regardless of arguments -- confirmed with
both literal-only calls and calls against real seeded `Document.embedding`
properties (also `null`), and regardless of whether a `vector` index
exists over the property (`CREATE INDEX doc_embedding_idx ON
Document(embedding) USING vector` itself succeeds).

**Fix applied**: none -- `bonus/vector_index.gql` keeps the post's exact
Solution GQL verbatim (both the `distance(...)` `WHERE` clause and the
`knn(...)` call). Both statements run without error and return `null`
results, which is itself the finding: this is not a parse-error case
like #1/#2/#6, it is a silent wrong-answer case, same category as #5.
"Fixing" the file to use `cosine()` instead would misrepresent what the
post's own recommended code actually does when run for real.

**Task 8 recommendation**: this is the most severe functional gap found
in this project -- an entire bonus tip's core functions
(`distance`/`similarity`/`knn`) do not work at all on this server build,
silently returning `null` instead of erroring. Until fixed upstream, the
"Use Vector Indexes for Similarity Search" bonus tip should either be
pulled from the post, rewritten around `cosine()` (the one function
confirmed to work), or given a prominent caveat that `distance`,
`similarity`, and `knn` are not yet functional.

## 10. `geode query` exits 0 even when the query itself errors (caught by the intentional-break test)

Not a blog-post inaccuracy -- a CLI/tooling gotcha that materially
affected this project's own `validate.sh` and is worth recording
explicitly, since the task brief specifically called out this bug
class and asked for it to be verified deliberately.

**Confirmed live**: a query-level error (parse error, grouping error,
etc.) prints `Error: ...` but the process exits `0`:

```text
$ geode query ... "MATCHX (n) RETURN n"; echo "EXIT: $?"
Error: parse error
EXIT: 0
```

Only connection/auth-level failures produce a non-zero exit:

```text
$ geode query ... --password wrongpassword "RETURN 1"; echo "EXIT: $?"
Error: Authentication failed
EXIT: 3
```

**How this was caught**: the task brief for this project specifically
warned about a bug class from Tasks 2-3's reviews where a
`validate.sh`/wrapper script's exit status gets masked, producing a
false PASS, and asked for a deliberate intentional-break test. The
first version of `validate.sh`'s `run_query()` here checked only the
`docker run` process exit code (correctly avoiding the *pipe-masking*
variant of this bug class documented in earlier tasks' FINDINGS.md) --
but that alone was insufficient: it broke `tips/04_use_limit.gql`
(`MATCH` -> `MATCHX`), ran `validate.sh`, and it printed `Error: parse
error` followed by `PASS: tips/04_use_limit.gql` -- a **different**
variant of the same false-PASS bug class, this time rooted in the CLI's
own exit-code semantics rather than a shell pipeline.

**Fix applied**: `run_query()` in `validate.sh` now also greps its
(leak-noise-filtered) output for a line-anchored `^Error:` and treats
that as failure independent of the exit code, alongside the exit code
check for connection/auth-level errors. Re-ran the intentional-break
test after the fix: `validate.sh` now correctly prints `FAIL:
tips/04_use_limit.gql` and exits non-zero; reverted the break,
`validate.sh` runs clean again (`ALL PASS`, exit 0).

**Task 8 recommendation**: not a post-content issue, but worth a note
to the Geode CLI team -- a query error that doesn't produce a non-zero
process exit is a footgun for any CI/script that checks `$?` alone
(exactly what happened here on the first attempt). Any GQL-in-CI
tooling built against this CLI needs the same output-text-based check
this project ended up using.
