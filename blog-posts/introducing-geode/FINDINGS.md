# Findings: `introducing-geode` example project

Validated against `geodedb/geode:latest` (confirmed v0.8.4) via the shared
Docker bootstrap in `../_shared/bootstrap.sh`. This file is the complete
input for fixing
[the blog post](https://codepros.org/blog/introducing-geode-a-modern-graph-database-for-the-quic-era/):
every snippet below that needed a change to work against a real server is
listed with its original form, the exact failure, and the corrected form.

For all five languages, two facts from Task 1 hold and explain most of what
follows:

1. **Auth is required on every connection.** The server has no anonymous
   access; every client must supply the `geode` user's credentials.
2. **TLS verification must be explicitly disabled for the dev container's
   self-signed certificate** (`insecure_tls_skip_verify=true` or the
   client's equivalent option). The post's snippets never show this.

The post's own DSN examples (`quic://localhost:3141`, no query params at
all) are written as if QUIC/TLS "just works" with zero configuration. That's
true for the *transport* (QUIC + TLS 1.3 negotiate automatically), but false
for *auth* and *certificate trust* against a real server -- both require
explicit DSN parameters the post never mentions in any language.

---

## 1. Go

**Post's snippet** (combining "Native Language Support" + "Getting
Started"):

```go
import "database/sql"
import _ "geodedb.com/geode"

db, err := sql.Open("geode", "quic://localhost:3141")
rows, err := db.Query("MATCH (p:Person) RETURN p")
```

with `CREATE (:Person {name: "Alice", age: 30})` run first via
`geode shell`/`geode query` per the Getting Started section (the post never
actually shows the Go driver issuing the CREATE).

**What happened running it as-is:** not run as-is (the discrepancy was
resolved before first run, per the task brief's explicit hypothesis) --
the driver's own DSN options (`?insecure_tls_skip_verify=true&user=...&pass=...`)
were used on the very first attempt and worked immediately. Confirmed by
elimination: the Go client's README documents `GEODE_HOST`/`GEODE_PORT`/
`GEODE_TLS_CA` as supported *environment variables* but not
`GEODE_USER`/`GEODE_PASSWORD` -- so DSN query params are the only way to
authenticate, not implicit env-var pickup.

**What had to change:** add `insecure_tls_skip_verify=true`, `user=`, and
`pass=` query parameters to the DSN.

**Corrected snippet** (`go/main.go`):

```go
dsn := fmt.Sprintf("quic://%s:%s?insecure_tls_skip_verify=true&user=%s&pass=%s",
    host, port, user, pass)
db, err := sql.Open("geode", dsn)
```

**Result:** `OK: 1 Person node(s) returned` (first run in an empty
container). Full sequence in `go/main.go`.

**Post fix needed:** every DSN example in the post (`quic://localhost:3141`)
should show the `insecure_tls_skip_verify`/`user`/`pass` params, at least in
a "for local development" callout, with a note that production deployments
should use `?ca=/path/to/ca.crt` instead of skipping verification.

---

## 2. Python

**Post's snippet:**

```python
from geode_client import open_database

client = open_database("quic://localhost:3141")
async with client.connection() as conn:
    page, _ = await conn.query("MATCH (p:Person) RETURN p")
    for row in page.rows:
        print(row)
```

**What happened running it as-is:** `client.connection()` raises immediately
on `__aenter__`:

```text
geode_client.client.AuthError: Authentication failed: Authentication required
```

i.e. `open_database()`/`Client.from_url()` establish the connection eagerly
inside the `async with` block, and the server rejects the handshake before
any query is even attempted, because the DSN carries no credentials or TLS
opt-out.

**First fix attempted (per the task brief's suggested fallback) and why it
was replaced:** adding a separate `AuthClient(conn).login(user, password)`
call after entering the `async with` block *cannot* work here, because the
`AuthError` is raised inside `client.connection().__aenter__()` itself --
the `async with` block body (where the `AuthClient` call would go) is never
reached. The real fix has to happen in the DSN, before the connection is
opened.

**What had to change:** two things, and the DSN option name is
Python-specific and does NOT match the other four clients:

1. Add `user=`/`pass=` query params to the DSN (same idea as Go, works the
   same way).
2. The Python client's TLS-skip-verification option is named **`skip_verify`**
   (`0`/`1`), not `insecure_tls_skip_verify` like the Go/Rust/Node/Zig
   clients. Confirmed from the client's own `Client.from_url()` docstring:
   `skip_verify: 0 or 1 (skip TLS verification)`. Using
   `insecure_tls_skip_verify=true` here is silently ignored (unknown DSN
   params are dropped, not rejected), which would leave TLS verification on
   and fail against the container's self-signed cert.

**Corrected snippet** (`python/getting_started.py`):

```python
dsn = (
    f"quic://{host}:{port}"
    f"?skip_verify=1&user={user}&pass={password}"
)
client = open_database(dsn)
async with client.connection() as conn:
    await conn.execute("CREATE (:Person {name: 'Alice', age: 30})")
    page, _ = await conn.query("MATCH (p:Person) RETURN p")
    for row in page.rows:
        print(row)
```

**Result:** `OK: 8 Person node(s) returned` (run after the other four
languages had already added their own Person nodes to the shared container
-- expected and noted in the script's own docstring; count grows with each
`validate.sh` run against the same container).

**Post fix needed:** the post's Python snippet needs `?skip_verify=1&user=
...&pass=...` on the DSN, called out as a *different* parameter name from
the Go/Rust/Node/Zig clients -- readers copy-pasting between language tabs
will otherwise hit exactly the `insecure_tls_skip_verify` mistake described
above.

---

## 3. Rust

**Post's snippet:**

```rust
use geode_client::Client;

let client = Client::connect("quic://localhost:3141").await?;
let result = client.query("MATCH (p:Person) RETURN p").await?;
```

**What happened running it as-is:** not run as written -- `Client::connect`
does not exist on the real (alpha, per the post's own maturity table) crate.
The real client's public API (confirmed against the crate's own README and
`examples/basic.rs`) is a builder: `Client::new(host, port)` (or
`Client::from_dsn(dsn)`), then a separate `.connect().await` call on the
built client to get a `Connection`, on which `.query()` is called. This is
a **blog-post bug independent of auth/TLS**: the snippet's API shape never
existed. This is expected for an alpha client per the post's own maturity
disclaimer, but the post's own code sample is still wrong and worth fixing
regardless of client maturity.

**What had to change:**

1. Use the real builder API: `Client::new(host, port).skip_verify(true)
   .username(user).password(pass)`, then `.connect().await?` to get a
   connection.
2. Auth: `.username()/.password()` builder methods, **not** DSN userinfo
   (`quic://user:pass@host:port`) -- the shared dev password contains
   spaces (see `../_shared/bootstrap.sh`'s password-policy comment), and
   URL userinfo would need percent-encoding to carry that safely. The
   builder methods take plain strings, so there's nothing to encode. (DSN
   userinfo does work for passwords without reserved characters -- this is
   a property of *this* deployment's password, not a client bug.)
3. TLS: `.skip_verify(true)`.

**Corrected snippet** (`rust/src/main.rs`):

```rust
let client = Client::new(&host, port)
    .skip_verify(true)
    .username(user)
    .password(pass);
let mut conn = client.connect().await?;
conn.query("CREATE (:Person {name: 'Alice', age: 30})").await?;
let (page, _) = conn.query("MATCH (p:Person) RETURN p").await?;
```

**Result:** `OK: 3 Person node(s) returned`.

**Client-maturity note (does not require a post fix beyond the API-shape
bug above):** none found beyond the nonexistent `Client::connect` API shape
-- once the real builder API was used, the client worked correctly on the
first successful attempt.

**Operational note, not a client bug:** an early validation run hit
`Error: Too many failed authentication attempts. Please try again later.`
from the server. Root-caused to repeated `source bootstrap.sh` invocations
during interactive debugging (each source re-runs bootstrap's own
`docker run ... query ... RETURN 1 AS health` sanity check, which counts
against the server's auth-attempt rate limit regardless of whether the
attempt succeeds), not to anything in the Rust code or client. `validate.sh`
sources bootstrap.sh exactly once per run, so this should not recur in
normal use; if it does, wait roughly 60-90 seconds and retry.

**Post fix needed:** replace `Client::connect("quic://...")` with the real
builder-based connect sequence, and add TLS/auth params, consistent with the
other languages.

---

## 4. Node.js

**Post's snippet:**

```ts
import { connect } from "@geodedb/client";

const client = await connect("quic://localhost:3141");
await client.withTransaction(async (tx) => {
  await tx.exec("CREATE (:Person {name: 'Alice'})");
});
```

**What happened running it as-is:** not run as written -- `connect` is not
exported by `@geodedb/client`; the real export (confirmed against the
client's own README and `src/index.ts`) is `createClient`. This is a
post bug independent of auth/TLS, for a client the post itself labels
**beta** (not alpha), so it is a real documentation defect to fix, not an
expected-maturity gap.

**What had to change (DSN/auth):**

An earlier version of this file used
`?insecure_tls_skip_verify=true&user=...&pass=...` query params and
asserted this was "the same shape as Go." That claim did **not** match the
real `geode-client-nodejs` README (re-fetched and re-read in full for this
fix pass, `main` branch, commit `4930cce8`). The README's DSN Format section
documents exactly one place for credentials:

```text
quic://[username:password@]host[:port][?options]   # QUIC transport (default port: 3141)
```

and its Options table (`page_size`, `hello_name`, `hello_ver`,
`conformance`, `graph`, `tenant`, `role`, `tls`,
`insecure_tls_skip_verify`, `ca`, `cert`, `key`, `server_name`,
`connect_timeout`, `request_timeout`) has **no** `user`/`pass` query-param
options at all -- the query-param form used in the earlier version of this
example was never documented and happened to work anyway (the client
apparently accepts undocumented query params without validation, or the
values were silently ignored and auth succeeded some other way -- not
investigated further since the README's own form works and should be
preferred).

**Live-validated fix:** switch to DSN userinfo, exactly as the README's own
"With authentication" example (`createClient('quic://admin:secret@localhost:3141')`)
shows, combined with `insecure_tls_skip_verify=true` for the dev cert:

```ts
const dsn = `quic://${encodeURIComponent(user)}:${encodeURIComponent(pass)}@${host}:${port}?insecure_tls_skip_verify=true`;
const client = await createClient(dsn);
```

`user`/`pass` are percent-encoded because the shared dev password contains
spaces, which are not valid raw characters in URL userinfo.

**Confirmed working against the live container** (`nodejs/index.mjs`,
`node index.mjs`):

```text
OK: 13 Person node(s) returned
```

(run standalone during this fix pass, before the full `validate.sh` re-run
below; count reflects Person nodes already accumulated in the shared
container from prior runs.)

**Client bug found (blocks the post's literal `RETURN p` operation, does
require documenting -- and arguably fixing upstream, since Node.js is
labeled *beta*, not alpha):** running the post's actual Getting Started
query, `MATCH (p:Person) RETURN p` (returning the whole node, as opposed to
individual properties), crashes every time with:

```text
_TransportError: geode: transport decode: Value is larger than Number.MAX_SAFE_INTEGER
    at longToNumber (.../dist/index.js:2396:11)
    ... (protobuf decode of a Node's `id` field, dist/index.js:4764)
```

Root cause: `@geodedb/client@1.1.0`'s wire decoder converts a graph node's
internal 64-bit `id` (a `uint64` protobuf field) to a JS `number` via a
`longToNumber()` helper that throws once the value exceeds
`Number.MAX_SAFE_INTEGER` (2^53 - 1). This server's node IDs are large
64-bit values (not small sequential integers), so **every** query that
returns a whole `Node` object -- not just this example's -- hits this,
regardless of what the application code does with the result; the crash
happens inside the client's own decode step before `queryAll()`/`query()`
ever returns to caller code. Confirmed the crash is specific to whole-node
decoding, not systemic: `RETURN count(p)` decodes fine (returns a plain
`cnt` scalar), and `RETURN p.name AS name, p.age AS age` (individual scalar
properties, sidestepping the node's `id` field entirely) also decodes fine.

**Workaround used** (`nodejs/index.mjs`): query `p.name`/`p.age` instead of
the whole node `p`:

```ts
const rows = await client.queryAll('MATCH (p:Person) RETURN p.name AS name, p.age AS age');
```

This is a real behavior change from the post's literal snippet (which
returns whole nodes), forced by the client bug above -- not a style choice.

**`withTransaction()` (the post's highlighted native-language feature):**
confirmed working once auth/TLS were fixed:

```ts
await client.withTransaction(async (tx) => {
  await tx.exec("CREATE (:Person {name: 'Alice', age: 30})");
});
```

**Result:** `OK: 7 Person node(s) returned`.

**Post fix needed (two independent issues):**

1. `connect` -> `createClient`, plus TLS/auth DSN params.
2. Either (a) change the post's own `MATCH (p:Person) RETURN p` example to
   return properties instead of the whole node, with a footnote about the
   decode bug for anyone on `@geodedb/client@1.1.0`, or (b) file/track the
   upstream bug (decode uses `BigInt` or a string instead of `Number` for
   uint64/int64 fields that don't fit in `Number.MAX_SAFE_INTEGER`) and
   update the post once fixed. Given the client is labeled *beta*, not
   *alpha*, this is a genuine defect worth tracking, not something the
   post's maturity disclaimer already excuses.

---

## 5. Zig

**Post's snippet:**

```zig
var client = try geode.Client.init(allocator, "localhost", 3141);
defer client.deinit();

var result = try client.query("MATCH (p:Person) RETURN p", .{});
defer result.deinit();
```

**What happened running it as-is:** not run as written -- `geode.Client`
does not exist. The module's real export is `GeodeClient`.

**Reconciliation pass (this fix): the client's own README Quick Start was
re-fetched and re-read in full** (`geode-client-zig`, `main` branch, commit
`0b4d1812`). It documents:

```zig
var client = geode.GeodeClient.init(allocator, "localhost", 3141, true);
// ...
try client.connect();
try client.openStream();
try client.sendHello("my-app", "1.0.0");
const response = try client.receiveMessage(30000);
// ...
try client.sendQuery("MATCH (n:Person) RETURN n.name, n.age");
const result = try client.receiveMessage(30000);
```

plus a separate `Config`/`.withCredentials(user, pass)` builder pattern
documented right below it. An earlier version of this file used a 7-arg
`GeodeClient.initWithTransport(allocator, host, port, insecure, username,
password, transport)` that appears **nowhere** in the README (it was
sourced from the client's integration tests instead) -- that claim is
replaced below with an actual reconciliation against the README, including
the real compiler errors hit along the way.

**Tried the README's exact Quick Start verbatim, compiled it against the
installed client (geode-client-zig 0.3.6), and it fails in two independent
ways:**

1. `std.heap.GeneralPurposeAllocator` doesn't exist in Zig 0.16 (renamed to
   `std.heap.DebugAllocator`) -- a Zig-version issue, not a client bug.
   After fixing that line to unblock further compilation:
2. `GeodeClient.init(allocator, "localhost", 3141, true)` -- the real
   compiler error:

   ```text
   src/main.zig:12:35: error: expected 6 argument(s), found 4
       var client = geode.GeodeClient.init(allocator, "localhost", 3141, true);
                    ~~~~~~~~~~~~~~~~~^~~~~
   .../geode_client_v2.zig:75:9: note: function declared here
       pub fn init(allocator: std.mem.Allocator, host: []const u8, port: u16, insecure: bool, username: []const u8, password: []const u8) !GeodeClient {
   ```

   The installed `init` requires `username`/`password` as required
   positional args (6 total) -- the README's 4-arg, no-credentials call
   never compiles against 0.3.6. `openStream()`, `sendHello(name, ver)`
   (2-arg), `receiveMessage()`, and `sendQuery()` as the README shows them
   are also not what's actually exported (the real, no-arg `sendHello()`
   was already confirmed in the earlier version of this file; the others
   were not individually re-verified once `init` itself failed to compile).

**Then tried the README's `Config`/`.withCredentials()` builder pattern**
(the second construction path the README documents, right below the Quick
Start) **against the same installed 0.3.6 package, correcting only the
parts that don't compile as literally written:**

- The README's `cfg.withHost("localhost")` / `cfg.withPort(3141)` don't
  exist as methods at all -- replaced with the real
  `Config.initWithHost(host, port)`, which combines both.
- The README's `cfg.withCredentials("admin", "secret")` (2 args, no `try`)
  doesn't match the real signature: `withCredentials(self: *Config,
  allocator: std.mem.Allocator, username: []const u8, password: []const
  u8) !*Config` -- it takes an allocator and returns an error union.
- Getting from a built `Config` to a `GeodeClient` isn't shown in the
  README at all; the real client exposes `GeodeClient.initFromConfig(
  allocator, cfg: config.Config) !GeodeClient` for exactly this.

**With those three corrections, the Config/withCredentials/initFromConfig
path -- which matches the README's *documented approach* (build a `Config`,
attach credentials via `.withCredentials()`, pass it to the client) even
though not its literal syntax -- compiles and runs successfully against the
live container:**

```text
OK: 15 Person node(s) returned
```

This is a real, working fix that stays much closer to what the README
actually documents than the previous `initWithTransport(...)` version of
this file, which does not appear in the README anywhere.

**Client-library documentation bug, worth noting separately from the blog
post's own inaccuracy:** `geode-client-zig`'s README Quick Start and Config
example are both stale relative to the installed 0.3.6 package -- `init()`
requires 2 more args than shown, `withHost`/`withPort` don't exist,
`withCredentials()` needs an allocator and a `try`, and `openStream()` /
`sendHello(name, ver)` / `receiveMessage()` / `sendQuery()` from the Quick
Start don't match the real API surface either (confirmed `sendHello()` is
no-arg; the other three were not directly re-verified since `init` itself
already failed to compile). This should be filed as a documentation bug
against `geode-client-zig` independent of the blog post fix.

**Post fix needed:** replace the fictional `geode.Client.init(...)` shape
with a `Config.initWithHost(host, port)` + `.withCredentials(allocator,
user, pass)` + `.withInsecure(true)` + `GeodeClient.initFromConfig(
allocator, cfg)` sequence, plus explicit `connect()` and `sendHello()`
(no args) before querying. Given the client is alpha, some API-shape churn
is expected per the post's own maturity disclaimer, but the post's code
should show real, compiling code regardless.

---

## Cross-language summary for Task 6 (post fixes)

| Language | Post's DSN/API bug | Auth/TLS params needed | Client-library bug (not a post fix) |
|----------|--------------------|--------------------------|--------------------------------------|
| Go | none (DSN just incomplete) | `insecure_tls_skip_verify=true&user=...&pass=...` | none found |
| Python | none (DSN just incomplete) | `skip_verify=1&user=...&pass=...` (**different param name than the others**) | none found |
| Rust | `Client::connect(dsn)` doesn't exist; real API is `Client::new(host, port)...connect()` | `.skip_verify(true).username(...).password(...)` (builder, not DSN userinfo -- password has spaces) | none found |
| Node.js | `connect` doesn't exist; real export is `createClient` | DSN userinfo `quic://user:pass@host:port?insecure_tls_skip_verify=true` (percent-encoded) -- the README documents credentials **only** via userinfo, no `user=`/`pass=` query params exist | **Yes** -- whole-node (`RETURN p`) decode crashes on 64-bit node IDs > `Number.MAX_SAFE_INTEGER`; post's `RETURN p` example must change to scalar properties, or wait for an upstream fix |
| Zig | `geode.Client.init(...)` doesn't exist as documented (README's 4-arg form doesn't compile against 0.3.6: real `init` needs 6 args); real working path is `Config.initWithHost(...)` + `.withCredentials(allocator, user, pass)` + `.withInsecure(true)` + `GeodeClient.initFromConfig(...)`, matching the README's *documented approach* once its stale method signatures are corrected | credentials via `Config.withCredentials()`, plus `.withInsecure(true)` for insecure TLS | **Yes** -- README's Quick Start and Config example are both stale relative to the installed 0.3.6 package (`init()` arg count, missing `withHost`/`withPort`, `withCredentials()` signature, `openStream()`/`sendHello(name,ver)`/`receiveMessage()`/`sendQuery()`) |

Every language's DSN needs *some* form of `insecure_tls_skip_verify`
(client-specific param name) plus credentials for local/dev use against
this server. The post should either add a single "Local development note"
callout near the top of the Getting Started section covering this, or annotate
each per-language snippet individually -- the cross-language table above
is intended to make either approach a copy-paste job from this file.
