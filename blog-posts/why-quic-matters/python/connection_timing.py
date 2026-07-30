"""Validates the "why-quic-matters" post's `measure_connection_time` example
from the "0-RTT Connection Resumption" section, verbatim in structure,
adapted only for auth. See ../FINDINGS.md for real captured timing numbers
from this environment.
"""

import asyncio
import os
import time

from geode_client import open_database


async def measure_connection_time() -> None:
    # See dashboard_concurrency.py for why credentials must be embedded in
    # the DSN rather than via a post-connect AuthClient.login() call.
    dsn = (
        f"quic://{os.environ['GEODE_HOST']}:{os.environ['GEODE_PORT']}"
        f"?insecure_tls_skip_verify=true&user={os.environ['GEODE_USER']}&pass={os.environ['GEODE_PASSWORD']}"
    )
    client = open_database(dsn)

    start = time.time()
    async with client.connection() as conn:
        await conn.query("MATCH (n) RETURN count(n)")
        first_time = time.time() - start

    start = time.time()
    async with client.connection() as conn:
        await conn.query("MATCH (n) RETURN count(n)")
        second_time = time.time() - start

    print(f"First connection: {first_time*1000:.1f}ms")
    print(f"Resumed connection: {second_time*1000:.1f}ms")


if __name__ == "__main__":
    asyncio.run(measure_connection_time())
