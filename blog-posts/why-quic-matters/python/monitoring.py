"""Validates (or, as it turns out, invalidates) the "why-quic-matters"
post's "Monitoring" section example: `client.get_connection_stats()`.

Live-tested against the real `geode-client` Python package: this method
does not exist on `Client` or `Connection`, and no equivalent
stats/metrics object is exposed anywhere on either class. See
../FINDINGS.md for the full `dir()` dump proving this and the
recommendation for what the post should say instead.
"""

import asyncio
import os

from geode_client import open_database


async def main() -> None:
    dsn = (
        f"quic://{os.environ['GEODE_HOST']}:{os.environ['GEODE_PORT']}"
        f"?insecure_tls_skip_verify=true&user={os.environ['GEODE_USER']}&pass={os.environ['GEODE_PASSWORD']}"
    )
    client = open_database(dsn)
    async with client.connection() as conn:
        await conn.query("RETURN 1 AS x")  # prove the connection itself works

        try:
            stats = await client.get_connection_stats()
            print(f"Protocol: {stats.protocol}")
            print(f"RTT: {stats.rtt_ms}ms")
            print(f"Active streams: {stats.active_streams}")
            print(f"Bytes sent: {stats.bytes_sent}")
            print(f"Packet loss: {stats.loss_rate}%")
        except AttributeError as e:
            print(f"NOT REAL: client.get_connection_stats() does not exist -- {e}")
            print(
                "Real public API surface on Client:",
                sorted(n for n in dir(client) if not n.startswith("_")),
            )
            print(
                "Real public API surface on Connection:",
                sorted(n for n in dir(conn) if not n.startswith("_")),
            )
            print(
                "OK: confirmed the post's Monitoring example is not "
                "implementable against the real 0.x geode-client package "
                "-- no connection/protocol statistics are exposed at all."
            )


if __name__ == "__main__":
    asyncio.run(main())
