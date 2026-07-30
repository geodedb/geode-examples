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

**What had to change (DSN/auth, same shape as Go):**

```ts
const dsn = `quic://${host}:${port}?insecure_tls_skip_verify=true&user=${encodeURIComponent(user)}&pass=${encodeURIComponent(pass)}`;
const client = await createClient(dsn);
```

`user`/`pass` are percent-encoded because, like the Rust case, the shared
dev password contains spaces; unlike Rust, the Node client's config API
only accepts credentials via the DSN (userinfo or query params), so
`encodeURIComponent` on the query-param values is the simplest safe path
(userinfo would also need it, plus bracket/escaping rules for the `@`
delimiter).

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
does not exist. The module's real export (confirmed against the crate's own
`tests/integration.zig`, which is authoritative here because it's
*executed* code -- unlike the README's Quick Start, which itself disagrees
with the integration tests on the constructor and handshake calls) is
`GeodeClient`, constructed via `GeodeClient.initWithTransport(allocator,
host, port, insecure, username, password, transport)`, not a 3-arg `init`.
This is expected for an **alpha** client per the post's own maturity
disclaimer -- the API-shape mismatch is a genuine finding, but doesn't
necessarily need a post fix beyond noting the real constructor name, since
alpha APIs are expected to move.

A second, separate mismatch: the client's own README Quick Start shows
`client.sendHello("my-app", "1.0.0")` (two args), but the client's own
integration test suite calls `client.sendHello()` with **no** arguments and
that's what actually compiles and works. This is an internal README/test
inconsistency in the client repo itself, not something to fix in the blog
post -- flagged here for whoever owns `geode-client-zig` next.

**What had to change:**

1. Real constructor: `GeodeClient.initWithTransport(allocator, host, port,
   true /* insecure */, username, password, Transport.quic)`.
2. Explicit handshake before querying: `try client.connect();` then
   `try client.sendHello();` (no args) -- the post's snippet queries
   immediately after `init`, with no connect/handshake step at all.
3. `std.heap.GeneralPurposeAllocator` does not exist in Zig 0.16 (renamed to
   `std.heap.DebugAllocator`) -- unrelated to the Geode client itself, a
   Zig-version issue for anyone following the post's Getting Started example
   verbatim with a current Zig toolchain. The post doesn't show allocator
   setup at all, so this is worth a one-line callout rather than a code
   change to the snippet itself.
4. Build setup: the client is not on any package registry (no
   `zig-pkg-manager`-style central index) -- it's added via
   `zig fetch --save=geode_client_zig
   "git+https://gitlab.com/devnw/codepros/geode/geode-client-zig.git#main"`,
   which also pulls a substantial private dependency graph (QUIC, TLS,
   thread-pool, GQL parser, etc., all from `gitlab.com/devnw/zig/*`). The
   consuming `build.zig` must also link `libc`, `ssl`, and `crypto` (Linux:
   `dl` too), mirroring the client's own `linkSystemDeps` helper -- this is
   undocumented in the client's own README, which shows only the
   `build.zig.zon`/`build.zig` snippet for declaring the dependency, not the
   system-library link requirement.

**Corrected snippet** (`zig/src/main.zig`):

```zig
var client = try GeodeClient.initWithTransport(
    allocator, host, port, true, username, password, Transport.quic,
);
defer client.deinit();
try client.connect();
try client.sendHello();

var result = try client.query("MATCH (p:Person) RETURN p", null);
defer result.deinit();
```

**Result:** `OK: 6 Person node(s) returned`, first successful run once the
real API and system-library links were in place.

**Client-maturity note (does not require a post fix per se, beyond noting
the real API):** the README Quick Start's `init`/`sendHello(name, ver)`
signatures are stale relative to the client's own integration tests --
worth flagging to the `geode-client-zig` maintainers, but the post's job is
just to show correct, working code, which it now does via the real,
tested API shape.

**Post fix needed:** replace the fictional `geode.Client.init(...)` /
2-arg `.query(...)` shape with the real `GeodeClient.initWithTransport(...)`
plus `connect()` plus `sendHello()` plus `query(gql, null)` sequence, and
add a one-line note that TLS/auth params are required (mirroring the other
four languages) plus the system-library link requirement for anyone building
their own `build.zig` against this client.

---

## Cross-language summary for Task 6 (post fixes)

| Language | Post's DSN/API bug | Auth/TLS params needed | Client-library bug (not a post fix) |
|----------|--------------------|--------------------------|--------------------------------------|
| Go | none (DSN just incomplete) | `insecure_tls_skip_verify=true&user=...&pass=...` | none found |
| Python | none (DSN just incomplete) | `skip_verify=1&user=...&pass=...` (**different param name than the others**) | none found |
| Rust | `Client::connect(dsn)` doesn't exist; real API is `Client::new(host, port)...connect()` | `.skip_verify(true).username(...).password(...)` (builder, not DSN userinfo -- password has spaces) | none found |
| Node.js | `connect` doesn't exist; real export is `createClient` | `insecure_tls_skip_verify=true&user=...&pass=...` (percent-encoded) | **Yes** -- whole-node (`RETURN p`) decode crashes on 64-bit node IDs > `Number.MAX_SAFE_INTEGER`; post's `RETURN p` example must change to scalar properties, or wait for an upstream fix |
| Zig | `geode.Client.init(...)` doesn't exist; real API is `GeodeClient.initWithTransport(...)` + explicit `connect()`/`sendHello()` | credentials passed directly to `initWithTransport`, plus `true` for insecure TLS | API-shape only (expected for alpha); README's own Quick Start disagrees with its integration tests |

Every language's DSN needs *some* form of `insecure_tls_skip_verify`
(client-specific param name) plus credentials for local/dev use against
this server. The post should either add a single "Local development note"
callout near the top of the Getting Started section covering this, or annotate
each per-language snippet individually -- the cross-language table above
is intended to make either approach a copy-paste job from this file.
