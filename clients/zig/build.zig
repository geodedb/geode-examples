const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    // Basic example
    const basic_exe = b.addExecutable(.{
        .name = "basic_example",
        .root_source_file = b.path("examples/basic/main.zig"),
        .target = target,
        .optimize = optimize,
    });
    b.installArtifact(basic_exe);

    // Transaction example
    const txn_exe = b.addExecutable(.{
        .name = "transaction_example",
        .root_source_file = b.path("examples/transactions/main.zig"),
        .target = target,
        .optimize = optimize,
    });
    b.installArtifact(txn_exe);

    // Run commands
    const run_basic = b.addRunArtifact(basic_exe);
    const run_step = b.step("run-basic", "Run basic example");
    run_step.dependOn(&run_basic.step);

    const run_txn = b.addRunArtifact(txn_exe);
    const run_txn_step = b.step("run-txn", "Run transaction example");
    run_txn_step.dependOn(&run_txn.step);
}
