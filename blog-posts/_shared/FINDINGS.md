# Server/CLI findings that apply across all four blog-post example projects

These affect every project under `blog-posts/*/` and are documented once
here instead of four times. All findings below were reproduced against a
live `geodedb/geode:latest` container (CLI/server `geode v0.8.4`), not
inferred from documentation.

## 1. The image's own default HEALTHCHECK is broken

`docker/health-check.sh` (baked into `geodedb/geode:latest`) runs
`geode query ... --insecure`. This CLI build hard-refuses
`--insecure-tls-skip-verify` (and its `--insecure` alias) under what it
calls "production conditions" unless `GEODE_ALLOW_INSECURE_TLS=1` is set
in the environment — which the image does not set by default. Result:
`docker run geodedb/geode:latest` with no extra flags never reports
`healthy`. Workaround: set `GEODE_ALLOW_INSECURE_TLS=1` on the container
(see docker-compose.yml). Confirmed: even with that var set, the
container's `docker inspect` health status never reliably transitions to
`healthy` in our testing — `bootstrap.sh` does not rely on Docker's
health status at all; it polls for the QUIC "listening" log line instead
(see section 3).

## 2. The server's own documented password-reset recovery path is a dead end

None of the four blog posts' "getting started" flows mention that a
fresh container requires authentication. In reality:

- The server generates a random password on first boot and writes it to
  `/data/.geode_admin_password` inside the container.
- The username to authenticate as is **`geode`** — not `admin`,
  despite the startup log calling it "admin password."
- That first login succeeds but every *query* is rejected with
  `Password reset required. Change password with: ALTER USER <username>
  SET PASSWORD '<new_password>'` — the server names its own recovery
  command in the error message.

**Following that instruction does not work.** We reproduced this
precisely, twice, from a clean container each time:

1. Read the auto-generated password from `/data/.geode_admin_password`.
2. Authenticate and run `ALTER USER geode SET PASSWORD '<new-pw>'`
   exactly as instructed. The CLI reports `Error: query execution
   failed` (not a policy-validation error — see below for what those
   look like).
3. Despite the client-visible error, the password *did* change: the old
   password now gets `Authentication failed`, and the new password gets
   accepted as a valid credential rather than rejected.
4. But running any subsequent query — including a trivial `RETURN 1`
   — with the *new*, now-valid password still returns `Password reset
   required`, identical to step 2. The `password_reset_required` flag is
   never cleared. The account is permanently locked out of running any
   normal query through this flow. Running `ALTER USER` again from this
   state repeats the same cycle indefinitely.

We also confirmed this is **specific to the forced-first-login-reset
state**, not a general `ALTER USER` bug: once an account is *not* in
`password_reset_required` state (e.g. because it was seeded via
`GEODE_ADMIN_PASSWORD`, see below), `ALTER USER <user> SET PASSWORD
'<new>'` works completely normally — the password changes and the very
next query with the new password succeeds immediately. The "query
execution failed" client message and the stuck flag only occur when
self-changing password out of the forced-reset state.

We also tried `geode user reset-password <user> --new-password <new>
--data-dir /data`, run via `docker exec` directly inside the *live*
server container (bypassing the network entirely). This subcommand
operates on-disk against the auth store independently of the running
server process and reports `Password reset for user 'geode'` — but the
running server's in-memory state does not see this write: a subsequent
network query with the "reset" password gets `Authentication failed`.
This path is unsafe to use against a live server and was abandoned.

**Working alternative (what `bootstrap.sh` actually uses):** setting the
`GEODE_ADMIN_PASSWORD` environment variable on the container *before its
first boot* seeds the admin account with that password directly and
skips the auto-generated-password/forced-reset flow entirely. Confirmed
end-to-end: the very first query against a container started this way
succeeds immediately with no `ALTER USER` step required. Note this seed
path does **not** enforce the password policy described below (a
one-word, 5-character password was accepted by the seed step) — we still
generate a policy-satisfying password for good practice, since later
projects' own GQL examples may want to demonstrate `ALTER USER` against
an already-active (non-reset-required) account, where the policy *is*
enforced.

**Confirmed password policy** (found by iterating on real `ALTER USER
... SET PASSWORD` validation error messages against an already-active,
non-reset-required account — this is the case where policy validation
actually runs before any write):

- Minimum 20 characters (`"Password too short (minimum 20 characters)"`).
- At least one uppercase letter
  (`"Password must contain at least one uppercase letter"`).
- At least one lowercase letter
  (`"Password must contain at least one lowercase letter"`).
- Must be a passphrase of at least 3 space-separated words
  (`"Password must be a passphrase with at least 3 words"`).
- No digit or special-character requirement was found — two different
  passphrases containing only letters and spaces (`Correct horse battery
  staple`, `Correct horse battery`) were both accepted.

This is a real, reproducible product bug worth filing against
`devnw/codepros/geode/geode` (not filed as part of this plan; flagged to
the user in this plan's final summary): **the server's own suggested
self-service recovery for the auto-generated first-boot admin password
does not work** — `ALTER USER` changes the credential but never clears
`password_reset_required`, permanently locking the account out via the
one path the server itself tells you to use.

## 3. Memory leak on every authenticated CLI request

Every successful `auth login` or authenticated `query` prints Zig
`DebugAllocator` leak reports to stderr, e.g.:

```text
error(DebugAllocator): memory address 0x7f7a82d20000 leaked:
/builds/devnw/codepros/geode/geode/zig-pkg/protobuf-0.1.4-0e82aqOEKgCEvqL9LJPtDWc4nzQ3LKAHmUzdiEWqo1-K/src/wire.zig:955:51: 0x1592775 in decodeMessage__anon_535851 (geode)
/builds/devnw/codepros/geode/geode/zig-pkg/protobuf-0.1.4-0e82aqOEKgCEvqL9LJPtDWc4nzQ3LKAHmUzdiEWqo1-K/src/wire.zig:1260:77: 0x1576101 in decodeMessage__anon_533383 (geode)
/builds/devnw/codepros/geode/geode/src/cli/main.zig:2542:39: 0x15ecdbd in readProtoMessageViaZigClient (geode)
/builds/devnw/codepros/geode/geode/src/cli/main.zig:3576:50: 0x15f3f81 in connectToServer (geode)
/builds/devnw/codepros/geode/geode/src/cli/cli_dispatcher.zig:312:30: 0x1247e73 in dispatch (geode)
/builds/devnw/codepros/geode/geode/src/cli/main.zig:3377:32: 0x124dc69 in main (geode)
/root/.zvm/0.16.0/lib/libc/musl/src/env/__libc_start_main.c:95:7: 0x1c24e07 in libc_start_main_stage2 (/root/.zvm/0.16.0/lib/libc/musl/src/env/__libc_start_main.c)
```

The command still succeeds and prints a correct result after the leak
dump — this does not block usage, but it is a real bug worth filing
against `devnw/codepros/geode/geode` (not filed as part of this plan;
flag it to the user in this plan's final summary). All example scripts
in this repo should filter it with
`grep -v 'DebugAllocator\|\.zig:\|libc_start\|additional stack'` when
capturing CLI output programmatically, so it isn't mistaken for a real
failure.

## 4. Hostname resolution over QUIC was unreliable in testing

Connecting via a docker-compose service name / container hostname did
not reliably resolve for the QUIC/UDP path when tested via
`docker network connect` + a separate throwaway container. Connecting
via the container's actual IP address (or via `--network container:`
network-namespace sharing) worked reliably. `bootstrap.sh` uses the IP
approach for `GEODE_HOST` and uses `--network container:<name>` for its
own internal sanity-check query. If a real docker-compose bridge
network's embedded DNS proves more reliable than the ad hoc network used
during this research, note that here and simplify `bootstrap.sh`
accordingly — don't assume without testing.

## 5. Host UDP port 3141 may already be in use on the validation host

Unrelated to the Geode server itself: on the host this plan was
validated on, UDP port 3141 was already bound by a process outside
Docker's/this sandbox's visibility (confirmed via `docker run -p
3141:3141/udp` failing with `address already in use`, and independently
via a raw Python `socket.bind(('0.0.0.0', 3141))` failing the same way,
with no owning process visible in `/proc/net/udp` without root). This is
host-specific and unrelated to the product. `docker-compose.yml`
publishes the container's UDP 3141 to host port `31413` instead to avoid
this; the container's *internal* port is unaffected and `bootstrap.sh`
never uses the host-published port anyway (it reaches the container via
`--network container:<name>` sharing, which talks to `127.0.0.1:3141`
inside the container directly). If port 3141 is free on your host, this
mapping can be changed back to `"3141:3141/udp"`.
