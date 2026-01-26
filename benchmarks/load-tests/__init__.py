# Load tests for Geode benchmarks
"""
Load testing scripts for Geode performance benchmarking.

Available tests:
- read_only: Verify 100,000 txn/sec read throughput claim
- read_write: Verify 10,000-50,000 txn/sec mixed throughput claim
- write_heavy: Verify 5,000-20,000 txn/sec write throughput claim
- concurrent_connections: Verify 10,000+ concurrent connections claim
- vector_distance: Verify <50ns vector distance latency claim
"""
