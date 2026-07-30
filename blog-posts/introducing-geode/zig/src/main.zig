// Runs the two operations from the "Introducing Geode" blog post's Getting
// Started section, using the Zig client shown in the post's "Native
// Language Support" section.
//
// The post's own snippet (`geode.Client.init(allocator, "localhost", 3141)`,
// `client.query(...)` returning a `result` you `.deinit()`) does not match
// the real (alpha) client's public API: there is no `geode.Client` type (the
// module exports `GeodeClient`), `init` alone does not take credentials (use
// `initWithTransport`, confirmed against the client's own integration test
// suite, not its README quick start -- the two disagree), and a handshake
// (`connect()` + `sendHello()`) is required before querying. See
// ../FINDINGS.md for the full story.

const std = @import("std");
const geode_client = @import("geode_client");
const GeodeClient = geode_client.GeodeClient;
const Transport = geode_client.config.Transport;

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

    var client = try GeodeClient.initWithTransport(
        allocator,
        host,
        port,
        true, // insecure: skip TLS verification -- self-signed dev cert
        username,
        password,
        Transport.quic,
    );
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
