// Runs the two operations from the "Introducing Geode" blog post's Getting
// Started section, using the Zig client shown in the post's "Native
// Language Support" section.
//
// The post's own snippet (`geode.Client.init(allocator, "localhost", 3141)`,
// `client.query(...)` returning a `result` you `.deinit()`) does not match
// the real (alpha) client's public API at all: there is no `geode.Client`
// type (the module exports `GeodeClient`).
//
// This file uses the client's own README-documented construction pattern --
// `Config` + `.withCredentials()` + passing the built `Config` to the
// client -- NOT the lower-level `GeodeClient.initWithTransport(...)` used in
// an earlier version of this example. Reconciled against the README with
// two real discrepancies found and worked around (see ../FINDINGS.md
// section 5 for the full story and the actual compiler errors):
//
//   1. The README's Quick Start calls `GeodeClient.init(allocator, host,
//      port, insecure)` (4 args, no credentials). The installed client
//      (geode-client-zig 0.3.6) requires `init(allocator, host, port,
//      insecure, username, password)` (6 args) -- confirmed by compiling
//      the README's exact snippet, which fails with "expected 6
//      argument(s), found 4".
//   2. The README's Config example calls `cfg.withHost(...)`,
//      `cfg.withPort(...)`, and `cfg.withCredentials("admin", "secret")`
//      (2 args). The installed client has no `withHost`/`withPort` methods
//      at all (use `Config.initWithHost(host, port)` instead), and the real
//      `withCredentials` signature is `withCredentials(self, allocator,
//      username, password) !*Config` -- it needs an allocator and returns
//      an error union, unlike the README's example.
//
// Once corrected for the real signatures, the Config/withCredentials/
// GeodeClient.initFromConfig() path -- which IS the README's documented
// approach in spirit, just not its literal syntax -- works correctly
// against a live server.

const std = @import("std");
const geode_client = @import("geode_client");
const GeodeClient = geode_client.GeodeClient;
const Config = geode_client.config.Config;

fn mustEnv(name: [*:0]const u8) []const u8 {
    if (std.c.getenv(name)) |v| return std.mem.span(v);
    std.debug.print("missing required env var: {s}\n", .{name});
    @panic("missing required env var");
}

pub fn main() !void {
    var gpa = std.heap.DebugAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    const host = mustEnv("GEODE_HOST");
    const port = try std.fmt.parseInt(u16, mustEnv("GEODE_PORT"), 10);
    const username = mustEnv("GEODE_USER");
    const password = mustEnv("GEODE_PASSWORD");

    // Config.initWithHost(host, port) replaces the README's nonexistent
    // cfg.withHost(...)/cfg.withPort(...) calls.
    var cfg = Config.initWithHost(host, port);
    defer cfg.deinit(allocator);
    // Real signature takes an allocator and returns !*Config (README's
    // example omits both).
    _ = try cfg.withCredentials(allocator, username, password);
    _ = cfg.withInsecure(true); // self-signed dev cert -- see bootstrap.sh

    var client = try GeodeClient.initFromConfig(allocator, cfg);
    defer client.deinit();

    try client.connect();
    try client.sendHello();

    {
        var create_result = try client.query("CREATE (:Person {name: 'Alice', age: 30})", null);
        defer create_result.deinit();
        if (create_result.hasError()) return error.CreateFailed;
    }

    var match_result = try client.query("MATCH (p:Person) RETURN p", null);
    defer match_result.deinit();
    if (match_result.hasError()) return error.QueryFailed;

    std.debug.print("OK: {d} Person node(s) returned\n", .{match_result.rows.items.len});
}
