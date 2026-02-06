const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    const geode_client_dep = b.dependency("geode_client", .{
        .target = target,
        .optimize = optimize,
    });
    const geode_client_mod = geode_client_dep.module("geode_client");

    // Basic example
    const basic_exe = b.addExecutable(.{
        .name = "basic_example",
        .root_module = b.createModule(.{
            .root_source_file = b.path("examples/basic/main.zig"),
            .target = target,
            .optimize = optimize,
            .imports = &.{
                .{ .name = "geode_client", .module = geode_client_mod },
            },
        }),
    });
    b.installArtifact(basic_exe);

    // Transaction example
    const txn_exe = b.addExecutable(.{
        .name = "transaction_example",
        .root_module = b.createModule(.{
            .root_source_file = b.path("examples/transactions/main.zig"),
            .target = target,
            .optimize = optimize,
            .imports = &.{
                .{ .name = "geode_client", .module = geode_client_mod },
            },
        }),
    });
    b.installArtifact(txn_exe);

    // Run commands
    const run_basic = b.addRunArtifact(basic_exe);
    const run_step = b.step("run-basic", "Run basic example");
    run_step.dependOn(&run_basic.step);

    const run_txn = b.addRunArtifact(txn_exe);
    const run_txn_step = b.step("run-txn", "Run transaction example");
    run_txn_step.dependOn(&run_txn.step);

    // Test step - verifies examples compile successfully
    const test_step = b.step("test", "Build and verify all examples");
    test_step.dependOn(&basic_exe.step);
    test_step.dependOn(&txn_exe.step);
}
