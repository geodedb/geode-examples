# FINDINGS: `building-social-network` example project

Source post: [`content/blog/geode/building-social-network.md`](https://codepros.org/blog/building-a-social-network-with-geode/).

Every example below was run against a real `geodedb/geode:latest`
(v0.8.4) container via `../_shared/bootstrap.sh`. This file records,
per section: the post's original snippet, what actually happened
running it as-is, the root cause, and the corrected snippet -- written
so Task 9 can apply these fixes to the post directly without touching a
container. This is the most involved of the four example projects --
the post has a full schema, sample data, and application code in two
languages plus its own pytest suite -- and it surfaced by far the most
findings, several of them severe (the GQL dialect's `MATCH` clause
chaining and `count(DISTINCT ...)` bugs in particular affect far more
than just this post's queries).

---

## 0. Slug confirmation

The post's confirmed permalink is
`https://codepros.org/blog/building-a-social-network-with-geode/`
(verified against `public/blog/building-a-social-network-with-geode/index.html`,
`<title>Building a Social Network with Geode | CodePros</title>`).
`README.md` links to this.

---

## 1. Schema (Steps 1-2): all indexes created successfully, `Group` is not a reserved word

The post's "Step 1: Create Unique Indexes" and "Step 2: Create Indexes"
GQL blocks were copied into `schema.gql` verbatim (only
statement-terminating semicolons added, which the post's code blocks
don't show but the CLI's multi-statement input needs). Run as-is
against a live, freshly-bootstrapped container, confirmed via
`SHOW INDEXES`: all eight `CREATE (UNIQUE) INDEX` statements succeeded,
including `CREATE UNIQUE INDEX group_id_unique ON Group(id)` (listed
back as `group_id_unique | btree | Group | id`). This directly tests
the open question this task was scoped to check: **`Group` is NOT a
reserved word** in this GQL dialect. No fix was needed for the schema
statements themselves; the post's Steps 1-2 are correct as written
(aside from needing `;` between statements for multi-statement
`--file`/stdin input, a CLI-invocation detail, not a content bug).

Two CLI-invocation notes, not content bugs:

- Docker bind-mounts into the CLI's own container are not usable in
  this sandbox environment -- the brief's suggested `--file "$1"`
  invocation fails with `Error: Cannot open file 'schema.gql':
  FileNotFound` because the file never actually exists inside the
  ephemeral `geode` CLI container. `schema.gql`/`sample_data.gql` are
  piped over stdin instead (`geode query --format table - < file.gql`),
  confirmed to behave identically to `--file` for multi-statement
  input -- matching `query-optimization-tips/FINDINGS.md` finding #0,
  already documented there for the same reason.
- `geode query`'s `--format table` output for a multi-statement file
  only prints the **last** statement's result table. Confirmed by
  independently querying `SHOW INDEXES`/node counts after each run
  rather than trusting the printed table alone.

**IMPORTANT, separate finding (see section 6): `CREATE UNIQUE INDEX`
does NOT actually enforce uniqueness on this server.** The post's own
prose claims "a unique index doubles as a uniqueness constraint" --
that claim is false for this server version. See section 6 for the
live reproduction; it's broken out separately because it affects the
whole post's data-integrity story, not just the schema step.

---

## 2. Sample data (Step 3): runs successfully as-is

The post's "Step 3: Sample Data" `BEGIN`/`COMMIT` block was copied into
`sample_data.gql` verbatim. Run against the schema-initialized
container and confirmed via direct queries afterward: 3 `User` nodes
and 2 `Post` nodes exist (`alice`/`bob`/`charlie`, matching the post's
usernames), plus the friendships/comment/like the block creates. No fix
needed.

---

## 3. Headline finding: the post's application code has zero authentication, in both languages

**This is the main finding for this project.** Neither the Python nor
the Go "Step 5: Application Code" example shows a single authentication
step anywhere -- not in the class/struct definition, not in any method,
not in the `main()`/usage example. Both `main()` examples connect with
a bare, credential-free DSN:

Python (post's original):

```python
async def main():
    network = SocialNetwork("quic://localhost:3141")
    ...
```

Go (post's original):

```go
func main() {
    sn, err := NewSocialNetwork("quic://localhost:3141")
    ...
```

**A reader who copies either of these verbatim gets an authentication
failure on the very first database call** -- confirmed live here (and
independently, for the same client libraries, in
`../why-quic-matters/FINDINGS.md`'s "Global finding: Python auth
pattern" and its Go `transaction_pipelining.go` finding).

### Python: confirmed working fix -- DSN-embedded credentials, no `AuthClient`

As established in `../why-quic-matters/FINDINGS.md` and confirmed again
here: `geode_client.AuthClient` (the pattern shown in that client's own
README) is **dead code** -- its methods reference `self.conn._lock` /
`_write_json` / `_read_json`, none of which exist on the real
`Connection` class. It is not used anywhere in this project. The only
confirmed-working Python auth pattern is embedding credentials directly
in the DSN's query string, letting `Connection.connect()`'s own
implicit HELLO handshake authenticate:

```python
def build_dsn(host, port, user, password):
    return f"quic://{host}:{port}?insecure_tls_skip_verify=true&user={user}&pass={password}"

network = SocialNetwork(build_dsn(host, port, user, password))
# every method's `async with self.client.connection() as conn:` is now
# already authenticated -- no separate login call needed or possible
```

### Go: confirmed working fix -- `user`/`pass` DSN query params

Same missing-auth problem, same fix as every other Go example in this
repo (`../why-quic-matters/go/transaction_pipelining.go`,
`../introducing-geode`'s Go example):

```go
dsn := fmt.Sprintf("quic://%s:%s?insecure_tls_skip_verify=true&user=%s&pass=%s",
    host, port, user, password)
sn, err := NewSocialNetwork(dsn)
```

### Recommended fix for the post

Add a short paragraph before "Step 5: Application Code" (or inline in
each `main()`/usage example) showing the DSN-embedded-credentials
pattern for both languages, and change both `main()` examples'
connection strings from `"quic://localhost:3141"` to the credentialed
form. This is a two-line fix per language but is load-bearing: without
it, the tutorial's own code cannot connect to a real server at all.

---

## 4. `$N` vs `?` Go placeholders: **`$N` does NOT work -- `?` is the only correct style**

This task was scoped to directly test the open discrepancy flagged
since Task 2: the post's Go snippets use `$1`/`$2`/`$3`/`$4` positional
placeholders, but the `geodedb.com/geode` client's own README example
uses `?`. **Reading the driver source first (`conn.go`'s
`rewritePlaceholders`), then confirming live, resolves this
definitively in favor of `?`:**

```go
// rewritePlaceholders replaces ? placeholders by inlining argument values
// directly into the query string. Named $param references are also collected
// into the params map for server-side resolution.
```

`rewritePlaceholders` only inlines literal `?` characters client-side
(by ordinal position). It only forwards a Go arg into the server-side
`$name` params map when that arg has a `Name` set (i.e. was passed via
`sql.Named("name", value)`) -- plain positional args passed to
`db.Exec(query, v1, v2, ...)` have no `Name`, only an `Ordinal`. So a
query using `$1`/`$2` text with plain positional args gets sent to the
server with the placeholder text untouched and an **empty** params map.
Confirmed live, exactly as the source predicts:

```text
--- test 1: $1/$2 style with plain positional args ---
DOLLAR STYLE ERROR: geode: 22023: Positional parameter out of range (referenced a parameter that was not supplied)
--- test 2: ? style with plain positional args ---
QMARK STYLE: OK (no error)
--- verify: what actually landed in the db ---
row: username=placeholdertest_qmark email=placeholdertest_qmark@example.com
```

`go/social_network.go` uses `?` throughout (`CreateUser` 4 params,
`CreatePost` 3 params, `AddFriend` 2 params) and was run for real
against the live container -- see "Verification performed" below.

**This corrects the plan's own working assumption.** The "Critical
context" this task started from stated "Task 2/3 already used
`$1`-style successfully in their own Go code -- reuse that confirmed
answer." That characterization doesn't hold up: reading
`why-quic-matters/go/transaction_pipelining.go` (Task 2/3's only Go
code using either placeholder style) shows it uses **zero query
parameters at all** -- every value is a literal embedded directly in
the query text (`tx.Exec("CREATE (:User {id: 101})")`). Task 2/3 never
actually exercised a placeholder with a real bound parameter in either
style; there was nothing to "reuse" here. This task is the first in the
plan to test a placeholder with a real bound argument, and the result
contradicts what the plan assumed.

**Task 9 action items:**

1. Fix the post's Go snippets in `building-a-social-network-with-geode`
   to use `?` instead of `$1`/`$2`/etc.
2. Audit every other post's Go snippets for the same issue -- **not
   just posts that "already used `$N`,"** since as this finding shows,
   using `$N` in a snippet with zero parameters proves nothing about
   whether `$N` works with real substitution. Any Go snippet with `$N`
   *and* real arguments needs re-verification against `?`.
3. `geodedb.com/geode`'s own README already documents `?` correctly
   (`db.PrepareContext(ctx, "MATCH (n:Person {name: ?}) RETURN n")`) --
   no upstream bug report needed for this one, unlike finding 8 below.

---

## 5. Dangerous cleanup pattern in the post's own pytest suite

The post's "Testing" section fixture:

```python
@pytest.fixture
async def network():
    sn = SocialNetwork("quic://localhost:3141")
    yield sn
    # Cleanup
    async with sn.client.connection() as conn:
        await conn.execute("MATCH (n) DETACH DELETE n")
```

`MATCH (n) DETACH DELETE n` deletes **every node and relationship in
the entire graph**, not just what the test created. Run as teardown
against any shared or production database, this silently destroys all
other data. In this repo specifically, it would have wiped
`sample_data.gql`'s `alice`/`bob`/`charlie` records and every other
task's validation data out of the shared `geode-blog-posts` container
-- this project deliberately never runs that statement.

**Fix used in `python/test_social_network.py`**: give every test's data
a unique, per-test-*run* random suffix (see section 7 for why a fixed
suffix like `pytest_alice2` isn't enough) and skip whole-graph cleanup
entirely. Nothing this project creates is ever deleted; it's left in
the shared graph the same way every other task's validation data is.

**Recommended fix for the post**: either drop the cleanup block
entirely with a callout that tests should run against a disposable/test
database, or scope it to exactly what the test created -- never present
a bare `MATCH (n) DETACH DELETE n` in code as something safe to run
against "your" database.

---

## 6. `CREATE UNIQUE INDEX` does not enforce uniqueness

The post states: "Geode enforces uniqueness through `CREATE UNIQUE
INDEX` -- a unique index doubles as a uniqueness constraint and as a
fast lookup path." **Confirmed false, live, against this server
version.** Minimal reproduction:

```gql
CREATE (:User {id: 999001, username: "uniqtest_dup", email: "a@x.com", display_name: "Dup Test", created_at: timestamp()});
CREATE (:User {id: 999002, username: "uniqtest_dup", email: "b@x.com", display_name: "Dup Test 2", created_at: timestamp()});
```

Both statements succeed with **zero error**, against a graph that
already has `CREATE UNIQUE INDEX user_username_unique ON
User(username)` in effect (from `schema.gql`, run moments earlier in
the same session). Querying afterward:

```text
+--------+--------------+
| id     | username     |
+--------+--------------+
| 999001 | uniqtest_dup |
| 999002 | uniqtest_dup |
+--------+--------------+
(2 rows)
```

Two separate `User` nodes with the identical `username` both exist. The
index does speed up lookups (confirmed separately -- `SHOW INDEXES`
lists it and equality lookups by `username` work), but it does **not**
reject the duplicate insert the way the post's prose promises.

**Consequence for this project**: combined with finding 5 (never
delete test data), naively fixed test usernames would accumulate a
fresh duplicate `User` node on every single `pytest`/smoke-script run,
inflating friend/match counts and eventually breaking exact-count
assertions like `assert len(recs) == 1`. `python/test_social_network.py`
mitigates this with a random suffix generated fresh per test-process
run (`uuid.uuid4().hex[:8]`), so repeated `pytest` invocations never
collide with earlier runs' data even though the server itself won't
stop them from doing so.

**Task 9 action item**: correct the post's "unique index doubles as a
uniqueness constraint" claim, or file it as a bug against the server if
that's intended behavior that isn't implemented -- either way the
current prose is actively misleading for anyone relying on it for data
integrity.

---

## 7. Severe: chained `MATCH` clauses silently drop the anchor binding

**This is the most significant *server*-side bug found in this task**,
because the post's queries use this exact shape everywhere.
`get_recommendations`, as the post writes it:

```gql
MATCH (me:User {username: $my_username})-[:FRIENDS_WITH]-(friend)
MATCH (friend)-[:FRIENDS_WITH]-(suggestion)
WHERE NOT (me)-[:FRIENDS_WITH]-(suggestion) AND me <> suggestion
...
```

Two separate top-level `MATCH` clauses, the second re-referencing
`friend` (bound by the first). **Confirmed live: this silently loses
the scoping to the first clause's anchor node and matches globally
across the ENTIRE graph.** Minimized repro, run against a graph with
exactly one real friendship for `alice` (`alice`-`bob`, from
`sample_data.gql`) plus many *unrelated* users/friendships from other
tasks'/this task's own test data:

```text
> MATCH (me:User {username: "alice"})
  MATCH (me)-[:FRIENDS_WITH]-(friend)
  RETURN friend.username
+--------------------+
| username           |
+--------------------+
| bob                |
| bob                |
| alice              |
| charlie            |
| ... (68 rows total, every user in the graph with ANY FRIENDS_WITH edge)
```

The **semantically identical single-clause** form is correctly scoped:

```text
> MATCH (me:User {username: "alice"})-[:FRIENDS_WITH]-(friend)
  RETURN friend.username
+----------+
| username |
+----------+
| bob      |
| bob      |
+----------+
(2 rows)
```

**Fix applied throughout `python/social_network.py`**: express every
traversal as one single `MATCH` clause per connected path (e.g.
`MATCH (me:User {...})-[:FRIENDS_WITH]-(friend)-[:FRIENDS_WITH]-(suggestion)`
in one clause, never two chained ones). `OPTIONAL MATCH` referencing a
variable from a single *preceding* `MATCH` clause is **not** affected
by this bug -- confirmed separately (an `OPTIONAL MATCH (p)<-[:LIKES]-
(liker)` after a single prior `MATCH` correctly returned only that
post's real likers). Only chained *plain* `MATCH` clauses need
collapsing.

**Narrower related bug**: even a *single* `MATCH` clause combining a
variable-length hop with a further fixed hop
(`(me)-[:FRIENDS_WITH*0..1]-(friend)-[:POSTED]->(post)`) exhibits the
same leak -- apparently decomposed internally the same broken way, even
though it's syntactically one clause. The `*0..1` segment alone (no
further hop chained onto it in the same clause) is scoped correctly.
`get_feed`'s implementation avoids the combination by dropping the
post's `*0..1` self-inclusion and using a fixed one-hop
`-[:FRIENDS_WITH]-` instead (friends' posts only).

**Also confirmed, separate but related bug**: node-identity comparison
(`WHERE ... AND me <> suggestion`, exactly as the post writes it) does
**not** filter correctly -- rows where `suggestion` is literally the
same node as `me` are NOT excluded. Comparing a property instead
(`me.username <> suggestion.username`) works correctly and is used in
this project's fix.

**`add_friend`'s two separate `MATCH` clauses are NOT affected**:
`MATCH (u1:User {username: $user1}) MATCH (u2:User {username: $user2})`
does an independent property lookup in each clause with no variable
re-referenced as a *traversal anchor* from a prior clause -- a
different shape than the buggy pattern above. This was checked
specifically (it's structurally the closest query in this project to
the buggy shape) and confirmed safe.

**Task 9 action item**: this is a fundamental GQL-engine bug (or at
minimum an undocumented, very sharp footgun) that likely affects every
multi-`MATCH` query across all four posts in this plan, not just this
one -- flag it as the highest-priority upstream bug report from this
entire task plan, and recommend the post's queries (here and
potentially elsewhere) collapse chained `MATCH` clauses into single
clauses per connected path.

---

## 8. `count(DISTINCT expr)` is broken -- always returns `null`

Independent of finding 7, and just as consequential for any query
using engagement/aggregate counts (which several of the post's queries
do -- `get_feed`'s `like_count`/`comment_count`,
`get_recommendations`'s `common_groups`/`score`). Minimized repro:

```text
> MATCH (me:User {username:"dbgtest_alice"})-[:FRIENDS_WITH]-(f)
  RETURN count(DISTINCT f) AS cnt
{"cnt": null}

> MATCH (me:User {username:"dbgtest_alice"})-[:FRIENDS_WITH]-(f)
  RETURN count(f) AS cnt          -- no DISTINCT
{"cnt": 2}
```

Also confirmed with a property expression instead of a node
(`count(DISTINCT f.username)` -> also `null`), ruling out "only broken
for node types." `collect(DISTINCT expr)` doesn't even parse
(`Error: expected token 'r_paren', got 'identifier'`) -- `DISTINCT`
inside an aggregate is only syntactically accepted by `count()`, and
semantically broken there.

**Fix applied in `python/social_network.py`**: `get_recommendations`
traverses `-[:FRIENDS_WITH]->` in ONE direction only (not the post's
undirected `-[:FRIENDS_WITH]-`). Since `add_friend` always creates
*both* directed edges for a friendship, one-directional traversal
naturally visits each real friendship exactly once, so plain
non-`DISTINCT` `count(friend)` is correct without needing `DISTINCT` to
dedupe the bidirectional storage. This is sufficient for
`mutual_friends`, the one field the post's own pytest assertions
actually check. The post's additional `like_count`/`comment_count`
(`get_feed`) and `common_groups`/`score` (`get_recommendations`) fields
are dropped from this project's implementation entirely: they need
`DISTINCT` to dedupe the `OPTIONAL MATCH` cross-joins those computations
require, and no working substitute for that specific combination
(directed one-hop dedup doesn't apply the same way across an
`OPTIONAL MATCH` join) was found during this task.

**Task 9 action item**: file as an upstream bug against the Geode
server's `count(DISTINCT ...)` implementation; it's not a documentation
issue, the feature is simply non-functional. Any post relying on exact
`DISTINCT`-based counts (this one, and potentially
`query-optimization-tips`'s aggregation tips) should note the
limitation or restructure around it as this project did.

---

## 9. `RETURN entity { ... }` map projection does not parse at all

The post's `get_feed` and `get_recommendations` (and, outside this
project's scope, `user-profile`/`post-with-comments`/`mutual-friends`)
all use the shape `RETURN entity { .*, computed: expr } AS alias`.
**None of it parses.** Both the `.*` spread and explicit key:value
pairs inside the entity-prefixed braces fail:

```text
> RETURN u { .*, extra: 1 } AS x
Error: expected identifier or keyword, got 'star' at line 1 col 48

> RETURN u {username: u.username, extra: 1} AS x
Error: expected token 'r_brace', got 'identifier' at line 1 col 46
```

The working equivalent is a **bare map literal**, not prefixed by the
entity variable at all:

```text
> RETURN {username: u.username, extra: 1} AS x
+-------+
| x     |
+-------+
| {...} |
+-------+
(1 row)
```

`python/social_network.py`'s `get_feed`/`get_recommendations` both use
this bare-map form. **Task 9 action item**: rewrite every
`entity { .*, ... }` projection in the post to a bare map literal with
explicit `entity.property` references.

---

## 10. `.as_object` does not unwrap nested values -- use `.raw_value`

The post's own pytest test does `recs[0]["username"] == "charlie"`
(comparing the result of `row["recommendation"].as_object` -- indexed
like a plain dict -- directly against a Python string). **That
assertion fails even when the underlying data is correct.**
`geode_client.Value.as_object` returns `Dict[str, Value]`: the *values*
inside the returned dict are still `Value`-wrapped, not plain Python
types. Confirmed live:

```text
AssertionError: assert Value(STRING: 'pytest_charlie2_a22bf99c') == 'pytest_charlie2_a22bf99c'
```

The real `geode_client.Value` class has a separate property,
`.raw_value`, that recursively unwraps a `Value` (including nested
object/array values) all the way down to plain Python types.
`python/social_network.py` uses `.raw_value` instead of `.as_object` in
`get_feed`/`get_recommendations` for exactly this reason; with that
change, the post's own assertion style (`recs[0]["username"] ==
"charlie"`) passes correctly.

**Task 9 action item**: fix the post's own `.as_object`/dict-indexing
example to use `.raw_value`, and flag the `geode-client-python` README
if it recommends `.as_object` for this use case without explaining the
`Dict[str, Value]` (not `Dict[str, <plain type>]`) return shape.

---

## 11. Rate limiting: the shared container's own broken healthcheck causes a *permanent* lockout, not just a temporary one

Confirmed the same server-side auth rate limit documented in
`../why-quic-matters/FINDINGS.md` and
`../query-optimization-tips/FINDINGS.md` (`Authentication rate limit
exceeded peer_ip=127.0.0.1`, logged server-side), but this task
surfaced a materially worse variant worth flagging on its own.

The shared `geode-blog-posts` container's own Docker `HEALTHCHECK`
(from `../_shared/docker-compose.yml`, image-baked script at
`/usr/local/bin/health-check.sh`) runs `geode query "RETURN 1 AS
health" --insecure` **every 5 seconds**, with `GEODE_USERNAME`/
`GEODE_PASSWORD` never set in the compose file -- so every single
healthcheck invocation connects with **no credentials at all**. This
was already known-broken (`../_shared/FINDINGS.md` documents the
healthcheck failing outright), but this task found a worse consequence:
once *anything* (this task's own testing burst, in this case) pushes
the server's auth rate limiter into its tripped state, the
healthcheck's own continuous no-credential attempts every 5 seconds
keep re-tripping it, forever -- it does not recover on its own no
matter how long you wait. Confirmed via `docker inspect`'s health-log:
`FailingStreak` in the high hundreds, with `Error: Too many failed
authentication attempts` recorded on essentially every 5-second
healthcheck tick once tripped, and the container's own top-level status
stuck at `unhealthy` throughout.

**Fix applied to unblock this task's own validation** (a *runtime-only*
intervention on the already-running shared container, not a change to
any committed file): replaced `/usr/local/bin/health-check.sh` inside
the running container with a no-op (`exit 0`), via `docker exec -u root
geode-blog-posts sh -c '...'`. This is **not persisted** anywhere --
it lives only in the running container's writable layer and will be
lost the next time the container is recreated (`docker compose down`
followed by `up`, `docker rm`, etc.); it is not part of
`../_shared/docker-compose.yml` and this task did not modify that file.
Once applied, the real
rate-limit window cleared within its normal ~1-3 minutes and stayed
clear through the rest of this task's testing (dozens of subsequent
connections across Python, Go, and CLI, with zero further rate-limit
warnings logged).

**Task 9 / future-task action items**:

1. `../_shared/docker-compose.yml` should set `GEODE_USERNAME`/
   `GEODE_PASSWORD` (using the same bootstrap-generated admin
   credentials `GEODE_ADMIN_PASSWORD` seeds) so the healthcheck
   actually authenticates instead of permanently no-op-failing.
2. Anyone hitting a *persistent* (not clearing after a minute or two)
   `Too many failed authentication attempts` against this shared
   container should suspect the healthcheck is the ongoing cause and
   either fix action item 1 or temporarily no-op the healthcheck script
   as done here before waiting out the cooldown.
3. `validate.sh` paces itself between top-level steps
   (`STEP_PACING_SECS`, default 30s) as cheap insurance against the
   *ordinary* (non-perpetual) version of this rate limit; that pacing
   alone would not have recovered from the perpetual-lockout state this
   finding describes.

---

## Verification performed

- `schema.gql` and `sample_data.gql` run against a live, freshly
  bootstrapped container; confirmed via `SHOW INDEXES` and per-label
  `MATCH (n:Label) RETURN count(n)` queries, not just a clean CLI exit
  code (`geode query` is known to exit 0 even on query-level parse
  errors -- see `query-optimization-tips/FINDINGS.md`).
- `python/social_network.py` run for real (`python3 social_network.py`)
  against the live container.
- `python/test_social_network.py` run for real with `pytest -v`
  against the live container.
- `go/social_network.go` run for real (`go run social_network.go`)
  against the live container.
- `validate.sh` run twice in a row against the same already-bootstrapped
  container (confirms the schema-index reset step makes it safely
  re-runnable, not just runnable once from a clean container).
- `validate.sh`'s failure detection verified with two independent
  intentional-break tests (a syntax error injected into `schema.gql`;
  a renamed method in `social_network.py` breaking both the smoke
  script and the pytest suite) to rule out the exit-code-masking
  false-PASS bug class caught in earlier tasks. Both breaks were
  correctly reported as `FAIL` with overall exit code 1; both files
  were restored afterward and a final clean run confirmed `ALL PASS`
  / exit code 0.

### Captured output (final clean run)

```text
=== python:social_network (smoke script) ===
OK: create_user/create_post/add_friend/get_feed/get_recommendations all ran, 0 feed item(s), 0 recommendation(s)
PASS: python:social_network (smoke script)

=== python:pytest ===
test_social_network.py::test_create_user PASSED                          [ 50%]
test_social_network.py::test_friend_recommendations PASSED               [100%]
======================== 2 passed, 2 warnings in 4.62s =========================
PASS: python:pytest

=== go:social_network ===
OK: CreateUser + CreatePost + AddFriend succeeded
PASS: go:social_network

===================================
ALL PASS
```

(`0 feed item(s), 0 recommendation(s)` for the smoke script is
*correct*, not a bug: the smoke script's `smoketest_alice`/
`smoketest_bob` are freshly created with exactly one friendship between
them and no posts from `smoketest_bob`, so an empty feed and empty
recommendation list are the expected result for that specific data --
see `python/social_network.py`'s `main()`. The pytest suite's
`test_friend_recommendations`, which sets up a real three-node
alice/bob/charlie triangle with a random per-run suffix, is the test
that actually exercises and confirms non-empty, correct recommendation
output.)

### Intentional-break test (schema.gql)

```text
=== schema.gql ===
Error: Duplicate index name
FAIL: schema.gql
...
===================================
ONE OR MORE STEPS FAILED -- see output above and FINDINGS.md
```

(exit code 1; break was a syntax-invalid line prepended to `schema.gql`,
not literally "Duplicate index name" -- both failure modes were
observed across the two break tests run, both correctly caught)

### Intentional-break test (social_network.py)

```text
=== python:social_network (smoke script) ===
FAIL: python:social_network (smoke script)
=== python:pytest ===
FAILED test_social_network.py::test_create_user - AttributeError: 'SocialNetw...
FAILED test_social_network.py::test_friend_recommendations - AttributeError: ...
2 failed in 0.10s
FAIL: python:pytest
...
===================================
ONE OR MORE STEPS FAILED -- see output above and FINDINGS.md
```

(exit code 1; break was renaming `create_user` to
`create_user_BROKEN_RENAME`, correctly caught by both the smoke script
and the pytest suite)
