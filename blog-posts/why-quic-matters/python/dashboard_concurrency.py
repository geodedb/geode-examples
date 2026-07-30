"""Validates the "why-quic-matters" post's "Multiple queries in parallel, no
blocking" example (the `get_dashboard_data` snippet in the "Stream
Multiplexing" section).

The post's own snippet calls `client.query(...)` directly (no connection
object, no auth) and awaits three bare coroutines with `asyncio.gather`.
Against a real server that requires auth on every connection, and against
the real `geode_client` API (queries run on a `Connection`, not a `Client`),
that fails. See ../FINDINGS.md for the full story; this file uses the
corrected connect+auth+query flow, still exercising the exact thing the
post is trying to demonstrate: `asyncio.gather` over `conn.query()` calls
sharing one QUIC connection.
"""

import asyncio
import os

from geode_client import open_database


async def main() -> None:
    # NOTE on auth: the post-connect `AuthClient(conn).login(...)` flow the
    # README documents for this client does NOT work against this server --
    # live-tested (see ../FINDINGS.md): it raises
    # `AuthError: Authentication failed: Authentication required` even with
    # correct credentials. Credentials must be embedded in the DSN itself,
    # exactly as confirmed for this client in ../../introducing-geode's
    # FINDINGS.md (`skip_verify`/`insecure_tls_skip_verify` are both
    # accepted as aliases; this file uses the README-documented
    # `insecure_tls_skip_verify` name).
    dsn = (
        f"quic://{os.environ['GEODE_HOST']}:{os.environ['GEODE_PORT']}"
        f"?insecure_tls_skip_verify=true&user={os.environ['GEODE_USER']}&pass={os.environ['GEODE_PASSWORD']}"
    )
    client = open_database(dsn)

    async with client.connection() as conn:
        # Seed enough data that the three queries below return non-trivial
        # counts. `timestamp()` is a real GQL function on this server.
        await conn.execute("CREATE (:User {id: 1, last_seen: timestamp()})")
        await conn.execute("CREATE (:Post {id: 1})")

        async def q(text: str):
            page, _ = await conn.query(text)
            return page

        users, posts, active = await asyncio.gather(
            q("MATCH (u:User) RETURN count(u) AS c"),
            q("MATCH (p:Post) RETURN count(p) AS c"),
            q("MATCH (u:User) WHERE u.last_seen > 0 RETURN count(u) AS c"),
        )
        print("users:", users.rows[0]["c"].as_int)
        print("posts:", posts.rows[0]["c"].as_int)
        print("active:", active.rows[0]["c"].as_int)

        # The post's own "Monitoring" section (further down in the post)
        # references `client.get_connection_stats()` with an `active_streams`
        # field as the way to confirm multiplexing actually happened rather
        # than the awaits silently serializing. Call it here and record
        # what really happens -- see ../FINDINGS.md for the monitoring.py
        # write-up with the full detail.
        try:
            stats = await client.get_connection_stats()
            print("connection stats:", stats)
        except AttributeError as e:
            print(
                "get_connection_stats() does not exist on the real client "
                f"({e}) -- cannot confirm true QUIC stream multiplexing "
                "occurred vs. the awaits serializing on one stream. This "
                "test only proves the API is callable this way and returns "
                "correct per-query results."
            )


if __name__ == "__main__":
    asyncio.run(main())
