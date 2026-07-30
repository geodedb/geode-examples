const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    const geode_client_dep = b.dependency("geode_client_zig", .{
        .target = target,
        .optimize = optimize,
    });
    const geode_client_mod = geode_client_dep.module("geode_client");

    const exe = b.addExecutable(.{
        .name = "introducing-geode-example",
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/main.zig"),
            .target = target,
            .optimize = optimize,
        }),
    });
    exe.root_module.addImport("geode_client", geode_client_mod);

    // QUIC/TLS transport links against OpenSSL, same as the client's own
    // build.zig (linkSystemDeps).
    exe.root_module.link_libc = true;
    if (target.result.os.tag != .windows) {
        exe.root_module.linkSystemLibrary("ssl", .{});
        exe.root_module.linkSystemLibrary("crypto", .{});
    }
    if (target.result.os.tag == .linux) {
        exe.root_module.linkSystemLibrary("dl", .{});
    }

    b.installArtifact(exe);

    const run_cmd = b.addRunArtifact(exe);
    run_cmd.step.dependOn(b.getInstallStep());

    const run_step = b.step("run", "Run the example");
    run_step.dependOn(&run_cmd.step);
}
