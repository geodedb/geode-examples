# FINDINGS: `why-quic-matters` example project

Source post: [`content/blog/geode/why-quic-matters.md`](https://codepros.org/blog/why-quic-matters-for-graph-databases/).

Every code example below was run against a real `geodedb/geode:latest`
(v0.8.4) container via `../_shared/bootstrap.sh`. This file records, per
example: the post's original snippet, what actually happened running it
as-is, the root cause, and the corrected snippet that actually works --
written so Task 7 can apply these fixes to the post directly without
touching a container.

## Global finding: Python auth pattern

Every one of the four Python examples below needed the same auth fix, so
it's documented once here instead of four times.

The post's snippets never show authentication (they're illustrative
fragments, not full runnable scripts), and the `geode-client-python`
README's own "Authentication" section documents this pattern:

```python
from geode_client import AuthClient

async with client.connection() as conn:
    auth = AuthClient(conn)
    session = await auth.login("username", "password")
```

**Live-tested against the real server, this does not work.** Connecting
with a DSN that has no credentials, then calling
`AuthClient(conn).login(user, pass)` inside the connection context,
raises immediately:

```text
FAILED: AuthError Authentication failed: Authentication required
```

i.e. the login call itself is rejected before it can establish a session.
This matches (and is now cross-confirmed by) `introducing-geode`'s
Python finding: credentials must be embedded in the DSN itself. Tested
and confirmed working:

```python
dsn = (
    f"quic://{host}:{port}"
    f"?insecure_tls_skip_verify=true&user={user}&pass={password}"
)
client = open_database(dsn)
async with client.connection() as conn:
    ...  # already authenticated, no AuthClient call needed
```

(The Python client's README documents `insecure_tls_skip_verify` in its
DSN Query Parameters table; `introducing-geode`'s Python finding found
`skip_verify` also works as an accepted alias. This project uses the
README-documented name.)

**Task 7 should note**: this may be a client library or server behavior
gap worth its own bug report (the README's own documented Authentication
flow doesn't work), separate from the blog post's inaccuracy -- but
fixing the blog post itself just means: show credentials in the DSN, not
a post-connect `AuthClient.login()` call.

---

## 1. `dashboard_concurrency.py` -- "Multiple queries in parallel, no blocking"

**Post's original snippet** (Stream Multiplexing section):

```python
# Multiple queries in parallel, no blocking
async def get_dashboard_data():
    # All execute concurrently on one connection
    users = client.query("MATCH (u:User) RETURN count(u)")
    posts = client.query("MATCH (p:Post) RETURN count(p)")
    active = client.query("MATCH (u:User) WHERE u.last_seen > $time RETURN count(u)")

    # Even if one query hits packet loss, others proceed
    return await asyncio.gather(users, posts, active)
```

**What happened running it as-is**: doesn't run at all. `client` here is
a bare `Client` from `open_database()`/`Client()` -- queries run on a
`Connection` (`async with client.connection() as conn: ... conn.query(...)`),
not directly on `Client`. `Client` has no `query` method (confirmed:
`dir(client)` is `['config', 'connect', 'connection', 'from_url', 'host',
'port', 'transport_type']` -- no `query`). There's also no
`$time` parameter binding shown being supplied, and (per the Global
Finding above) no auth.

**Root cause**: post-simplification for readability dropped the
`Connection` object and the auth step that a runnable version needs.

**Corrected snippet** (live-validated, real output `users: 4 / posts: 2 /
active: 2` on the shared dev container -- counts include prior runs since
data accumulates across `validate.sh` runs, see README.md):

```python
import asyncio
import os
from geode_client import open_database

async def main():
    dsn = (
        f"quic://{os.environ['GEODE_HOST']}:{os.environ['GEODE_PORT']}"
        f"?insecure_tls_skip_verify=true&user={os.environ['GEODE_USER']}&pass={os.environ['GEODE_PASSWORD']}"
    )
    client = open_database(dsn)
    async with client.connection() as conn:
        await conn.execute("CREATE (:User {id: 1, last_seen: timestamp()})")
        await conn.execute("CREATE (:Post {id: 1})")

        async def q(text):
            page, _ = await conn.query(text)
            return page

        users, posts, active = await asyncio.gather(
            q("MATCH (u:User) RETURN count(u) AS c"),
            q("MATCH (p:Post) RETURN count(p) AS c"),
            q("MATCH (u:User) WHERE u.last_seen > 0 RETURN count(u) AS c"),
        )
        print("users:", users.rows[0]["c"].as_int)
        print("posts:", posts.rows[0]["c"].as_int)
        print("active:", active.rows[0]["c"].as_int)

asyncio.run(main())
```

**What this proves, and what it can't** (per the task brief's own
caveat): `asyncio.gather` over three `conn.query()` calls on the same
`conn` proves the API is callable this way and returns correct
per-query results. It does **not** by itself prove three independent
QUIC streams were used rather than one connection serializing the
awaits. The only way to actually confirm multiplexing (not just
functional correctness) would be `client.get_connection_stats()`'s
`active_streams` field -- see finding 4 below: **that method does not
exist on the real client**, so this cannot currently be confirmed by any
means available in the client library. `dashboard_concurrency.py` calls
it anyway (catching the resulting `AttributeError`) to make this
limitation visible in the script's own output, not just in this doc.

**Task 7 recommendation**: fix the snippet to use `conn.query()` inside
`async with client.connection()`, and add a sentence noting that this
example demonstrates the *functional* API, not a verified proof of
stream-level multiplexing (which the client currently has no way to
expose).

---

## 2. `connection_timing.py` -- `measure_connection_time` (0-RTT section)

**Post's original snippet**: shown in full in the post's "0-RTT
Connection Resumption" section; reproduced verbatim in structure in
`python/connection_timing.py` except for the DSN.

**What happened running it as-is**: the post's DSN
(`quic://localhost:3141`, no auth) fails immediately with an auth error
against this server -- same Global Finding as above.

**Root cause**: DSN missing auth (illustrative snippet, not written
against an auth-required server).

**Corrected snippet**: identical to the post's function body, with the
DSN construction from the Global Finding substituted in. See
`python/connection_timing.py` for the full file.

**Real numbers captured** (four separate runs against the shared dev
container, single-process short-lived script, localhost/Docker network):

| Run | First connection | Resumed connection |
|-----|-------------------|---------------------|
| 1   | 89.5ms            | 47.3ms              |
| 2   | 115.3ms           | 44.5ms              |
| 3   | 100.7ms           | 56.6ms              |
| 4   | 121.2ms           | 57.3ms              |

**Shape check**: the resumed connection is consistently and substantially
faster than the first (roughly 45-60% of the first connection's time)
across every run. This confirms the *qualitative* shape the post claims
holds. It does **not** confirm the specific 0-RTT protocol mechanism is
what's producing the speedup as opposed to, e.g., OS-level connection
caching, warm code paths, or Docker network warmup on a repeat call in
the same process -- the post itself already correctly labels its own
numbers as illustrative/not measured, and this test doesn't change that
disclaimer's validity. What it adds is: on this real server, the
directional claim ("second connection meaningfully faster") is
consistently true, not just theoretical.

**Task 7 recommendation**: no change needed to the post's own numbers
(already correctly caveated); this finding is confirmatory, not
corrective.

---

## 3. `stream_large_result.py` -- streaming results

**Post's original snippet** (Efficient Result Streaming section):

```python
async def stream_large_result():
    result = await client.query("""
        MATCH (p:Person)
        WHERE p.country = 'USA'
        RETURN p
        LIMIT 1000000
    """)
    async for row in result:
        process(row)  # Low memory, low latency
```

**What happened running it as-is**: two independent breaks, both
confirmed live:

1. `client.query(...)` -- same `Client`-vs-`Connection` issue as finding
   1; `client` has no `query` method.
2. Even fixed to `conn.query(...)`, the return value is not something you
   can `async for row in result:` over. `conn.query()` returns a
   `(Page, pager)` tuple (`page.rows` is the first page's row list;
   `pager()` returns an async iterator of subsequent `Page`s). There is
   no direct per-row async iterator returned by `query()` itself.

**Root cause**: the post's `async for row in result:` describes a
streaming *mental model* the client doesn't literally implement -- the
real API is page-based pagination via a separate `pager()` callable
(confirmed against the client's own README "Pagination" section, and
now confirmed working live).

**Seeding also needed a fix**: the brief's suggested seed statement,
`UNWIND range(0, 999) AS i CREATE (:Person {id: i, country: 'USA'})`,
does not parse on this server at all -- confirmed with a live error even
on the simplest possible case:

```text
UNWIND [1,2,3] AS i RETURN i
-> QueryError: 42000: parse error
```

`UNWIND` is not implemented in this server's GQL dialect (not listed in
the syntax reference; every `UNWIND` variant tried failed to parse).
Worked around by seeding via a single `CREATE` statement with 1000
comma-separated node patterns instead (confirmed working: `CREATE
(:Person {id: 0, country: 'USA'}), (:Person {id: 1, ...}), ...`).

**Corrected snippet** (live-validated, real output `streamed 1000 rows
across 1 page(s)`):

```python
async def stream_large_result():
    dsn = (...)  # see Global Finding
    client = open_database(dsn)
    async with client.connection() as conn:
        patterns = ", ".join(
            f"(:Person {{id: {i}, country: 'USA'}})" for i in range(1000)
        )
        await conn.execute(f"CREATE {patterns}")

        page, pager = await conn.query(
            "MATCH (p:Person) WHERE p.country = 'USA' RETURN p LIMIT 1000",
            page_size=100,
        )
        count = len(page.rows)
        async for next_page in pager():
            count += len(next_page.rows)
        print(f"streamed {count} rows")
```

**A note on what this does and doesn't prove about streaming**: the
result came back as a single page (`pages: 1`) even though `page_size=100`
was explicitly requested and the payload was padded to ~2MB in a separate
test to try to force multi-page chunking -- it still didn't. Reading the
installed client's source (`geode_client/client.py`), `page_size` is
only used for subsequent `PULL` requests via the pager; it is not sent
as part of the initial query request, so the *first* page's size is
determined entirely server-side. On this server, for this data volume,
the server evidently doesn't chunk. This means `pager()` is confirmed
real and functionally correct (it returns the right total, and
correctly returns an empty async iterator when there's nothing more to
pull), but this test -- and, likely, the post's own `LIMIT 1000000`
version -- may not actually exercise true multi-RPC streaming without a
significantly larger result set or different page-size configuration
than was tried here. Task 7 should soften "results arrive in chunks via
QUIC streams" to something that doesn't imply this is guaranteed for
mid-size result sets, or note that chunking threshold behavior is
server-controlled and untested at post-published scale.

**Task 7 recommendation**: fix `async for row in result:` to the
page/pager pattern shown above; fix or drop the `UNWIND`-based seeding if
the post ever shows seed code (it currently doesn't, this was only
needed for this example project); soften the "streams in chunks" claim
per the note above.

---

## 4. `monitoring.py` -- `client.get_connection_stats()`

**Post's original snippet** (Monitoring section):

```python
# Check connection statistics
stats = await client.get_connection_stats()

print(f"Protocol: {stats.protocol}")  # "quic"
print(f"RTT: {stats.rtt_ms}ms")
print(f"Active streams: {stats.active_streams}")
print(f"Bytes sent: {stats.bytes_sent}")
print(f"Packet loss: {stats.loss_rate}%")
```

**What happened running it as-is**: fails immediately.

```text
AttributeError: 'Client' object has no attribute 'get_connection_stats'
```

**Confirmed this is not just a naming difference** -- checked for any
equivalent attribute or method anywhere on both public classes involved
in a query, live-introspected via `dir()`:

```text
Client public API:     ['config', 'connect', 'connection', 'from_url', 'host', 'port', 'transport_type']
Connection public API: ['batch', 'batch_exec', 'begin', 'ca_cert', 'client_cert', 'client_key', 'close',
                         'commit', 'conformance', 'connect', 'execute', 'explain', 'fetch_one', 'graph',
                         'hello_name', 'hello_ver', 'host', 'page_size', 'password', 'pipeline_exec', 'port',
                         'prepare', 'profile', 'query', 'query_row', 'role', 'rollback', 'rollback_to',
                         'savepoint', 'server_name', 'skip_verify', 'tenant', 'tls_enabled', 'transport_type',
                         'username']
```

Also cross-checked against the `geode-client-python` README's own "API
Reference / Core Classes" table (`Client`, `Connection`, `Page`, `Value`,
`QueryBuilder`, `PatternBuilder`, `PredicateBuilder`, `ConnectionPool`,
`AuthClient`, `TransportType`) -- no stats/metrics class is documented
there either. **There is no partial or renamed equivalent.** No
protocol name, RTT, active-stream-count, bytes-sent, or packet-loss data
is exposed anywhere in the public API of the real 0.x `geode-client`
Python package.

**Root cause**: this is not a naming mismatch like most of the other
findings in this project (and in `introducing-geode`) -- the entire
feature this section describes does not exist in the client library
today. This looks like the post was written against a planned/aspirational
API surface, not one that ever shipped.

**Recommendation for Task 7 (per the brief's explicit instruction not to
force a fake pass)**: the post's "Monitoring" section needs one of:

1. **Remove it entirely** until the client library actually ships
   connection statistics, or
2. **Replace it with an honest caveat**, e.g.: "Per-connection QUIC
   statistics (RTT, active streams, bytes sent, packet loss) are not
   currently exposed by the official client libraries. To observe these
   properties today, use OS-level tools (`ss -u`, packet captures) or the
   server's own structured JSON logs (`--log-json`), which report
   `active_streams` at the connection level -- see the sample log line
   observed live in this project's own container output:
   `info: metrics: msgs_delivered+=1 total=... active_streams=N
   proto_idle_ms=...`." That server-side log line is real -- it is the
   closest thing to the post's claimed feature that actually exists
   today.
3. File a feature request against `geode-client-python` (and likely the
   other clients) to expose connection/transport statistics, since the
   server itself clearly tracks this data (option 2's log line proves
   it) -- the gap is entirely in the client library's public API, not
   the server's capabilities.

Recommend option 2 combined with 3: keeps the post accurate today while
giving the underlying idea (QUIC connections are observable) a real,
working example instead of a fabricated one.

---

## 5. `go/transaction_pipelining.go` -- Transaction Pipelining

**Post's original snippet** (Transaction Pipelining section):

```go
// All operations sent in parallel, executed serially
tx, _ := client.Begin()

// These can all be sent before waiting for responses
tx.Execute("CREATE (:User {id: 1})")
tx.Execute("CREATE (:User {id: 2})")
tx.Execute("MATCH (u1:User {id: 1}), (u2:User {id: 2}) CREATE (u1)-[:KNOWS]->(u2)")

// QUIC streams allow all to be in flight
tx.Commit()  // Wait for all to complete
```

**What happened compiling it as-is** (using the real `geodedb.com/geode`
`database/sql` driver, with `client` typed as `*sql.DB` per the rest of
the post's Go examples, e.g. the "Always Encrypted" section's
`db, err := sql.Open("geode", ...)`):

```text
./main.go:25:5: tx.Execute undefined (type *sql.Tx has no field or method Execute)
./main.go:26:5: tx.Execute undefined (type *sql.Tx has no field or method Execute)
./main.go:27:5: tx.Execute undefined (type *sql.Tx has no field or method Execute)
```

(`client.Begin()` itself is fine -- `*sql.DB` does have a `Begin()`
method, it's the standard library's own. The bug is `tx.Execute`, not
`client.Begin`.)

**Root cause**: `database/sql`'s real interface is `db.Begin() (*sql.Tx,
error)` then `tx.Exec(query, args...) (sql.Result, error)` -- no
capital-E `Execute` method exists on `*sql.Tx` in the standard library,
and this driver doesn't add one.

**Corrected snippet** (live-validated, real output `OK: transaction
committed`):

```go
package main

import (
 "database/sql"
 "fmt"
 "log"
 "os"

 _ "geodedb.com/geode"
)

func main() {
 dsn := fmt.Sprintf("quic://%s:%s?insecure_tls_skip_verify=true&user=%s&pass=%s",
  os.Getenv("GEODE_HOST"), os.Getenv("GEODE_PORT"), os.Getenv("GEODE_USER"), os.Getenv("GEODE_PASSWORD"))

 db, err := sql.Open("geode", dsn)
 if err != nil {
  log.Fatal(err)
 }
 defer db.Close()

 tx, err := db.Begin()
 if err != nil {
  log.Fatal(err)
 }

 if _, err := tx.Exec("CREATE (:User {id: 101})"); err != nil {
  tx.Rollback()
  log.Fatal(err)
 }
 if _, err := tx.Exec("CREATE (:User {id: 102})"); err != nil {
  tx.Rollback()
  log.Fatal(err)
 }
 if _, err := tx.Exec("MATCH (u1:User {id: 101}), (u2:User {id: 102}) CREATE (u1)-[:KNOWS]->(u2)"); err != nil {
  tx.Rollback()
  log.Fatal(err)
 }

 if err := tx.Commit(); err != nil {
  log.Fatal(err)
 }
 fmt.Println("OK: transaction committed")
}
```

**What this proves, and what it can't**: this confirms the transaction
API surface (`Begin`/`Exec`/`Commit`/`Rollback`) is real and works
end-to-end, including a multi-statement transaction with a relationship
that depends on both prior statements having committed within the same
transaction. It does not by itself prove the *pipelining* claim (that
`database/sql`'s standard blocking `Exec` calls are actually being sent
without waiting for each response, i.e. genuinely pipelined over QUIC
streams rather than sent-and-awaited one at a time) -- `database/sql`'s
public interface is synchronous per-call by design, so nothing in this
corrected example can distinguish "pipelined under the hood" from
"sequential but fast." That distinction would need driver-internal
instrumentation or a packet capture, out of scope for this project.

**Task 7 recommendation**: fix `client.Begin()` (only correct if
`client` is explicitly typed/introduced as `*sql.DB`, which the post's
snippet never shows -- add that context) and `tx.Execute(...)` ->
`tx.Exec(...)`; consider softening the "sent in parallel" /
"pipelining" framing in the surrounding prose to avoid implying a
guarantee that `database/sql`'s synchronous interface cannot make.

---

## Findings summary (for Task 7)

| # | Example | Bug class | Fix |
|---|---------|-----------|-----|
| Global | All Python examples | Documented `AuthClient.login()` auth flow doesn't work live | Embed `user=`/`pass=` in DSN instead |
| 1 | `dashboard_concurrency.py` | `client.query()` doesn't exist; no `Connection` shown | Use `async with client.connection() as conn: ... conn.query(...)` |
| 2 | `connection_timing.py` | DSN missing auth | Same as Global finding; numbers confirmed directionally correct |
| 3 | `stream_large_result.py` | `async for row in result` isn't the real streaming API; `UNWIND` doesn't parse on this server | Use `page, pager = await conn.query(...)`; seed via multi-pattern `CREATE` |
| 4 | `monitoring.py` | `client.get_connection_stats()` does not exist anywhere in the client's public API | Remove/replace section; server-side JSON logs are the real (if not equivalent) alternative |
| 5 | `go/transaction_pipelining.go` | `client.Begin()`/`tx.Execute()` isn't `database/sql`'s real interface | `db.Begin()`/`tx.Exec()`/`tx.Commit()` (the only method actually wrong is `Execute`->`Exec`) |
