// Runs the two operations from the "Introducing Geode" blog post's Getting
// Started section, using the Node.js client shown in the post's "Native
// Language Support" section.
//
// The post's own snippet (`import { connect } from '@geodedb/client'`, then
// `connect('quic://localhost:3141')`) does not match the real client: the
// real export is `createClient`, not `connect`, and the DSN needs TLS/auth
// params against a real server. See ../FINDINGS.md for the full story.
//
// Auth is passed as DSN userinfo (`user:pass@host`), matching the real
// client's README (DSN Format: `quic://[username:password@]host[:port]
// [?options]`; the Options table has no `user`/`pass` query params at all).
// user/pass are percent-encoded because the shared dev password contains
// spaces (see bootstrap.sh) and raw spaces/reserved characters are not
// valid in URL userinfo.
//
// IMPORTANT: this queries `p.name`/`p.age` rather than the whole node `p`
// (which is what the post's own snippet returns). Returning the whole node
// hits a confirmed decode bug in @geodedb/client 1.1.0 -- the wire decoder
// converts a graph node's internal 64-bit `id` with a lossy/throwing
// `longToNumber()` instead of BigInt, and this server's node IDs exceed
// Number.MAX_SAFE_INTEGER, so decoding ANY `RETURN p` (whole node) result
// throws `TransportError: Value is larger than Number.MAX_SAFE_INTEGER`
// before application code ever sees a row. See ../FINDINGS.md for the full
// repro and upstream bug writeup.

import { createClient } from '@geodedb/client';

const host = mustEnv('GEODE_HOST');
const port = mustEnv('GEODE_PORT');
const user = encodeURIComponent(mustEnv('GEODE_USER'));
const pass = encodeURIComponent(mustEnv('GEODE_PASSWORD'));

const dsn = `quic://${user}:${pass}@${host}:${port}?insecure_tls_skip_verify=true`;

const client = await createClient(dsn);

// The post's "Native Language Support" section highlights `withTransaction()`
// as the Node client's distinctive feature (wraps begin/commit/rollback
// around a callback), so the CREATE runs through it rather than a bare
// `client.exec()`.
await client.withTransaction(async (tx) => {
  await tx.exec("CREATE (:Person {name: 'Alice', age: 30})");
});

const rows = await client.queryAll('MATCH (p:Person) RETURN p.name AS name, p.age AS age');
console.log(`OK: ${rows.length} Person node(s) returned`);

await client.close();

function mustEnv(name) {
  const v = process.env[name];
  if (!v) {
    throw new Error(`missing required env var: ${name}`);
  }
  return v;
}
