"""Validates the "why-quic-matters" post's streaming example from the
"Efficient Result Streaming" section, scaled down from `LIMIT 1000000` to
1000 rows a local test can actually seed quickly.

Two things needed correcting from the post's snippet -- see
../FINDINGS.md for the full detail:

1. The post's `async for row in result:` is not how this client streams
   results. The real API is `page, pager = await conn.query(...)`, then
   iterate `page.rows` for the first page and `async for next_page in
   pager():` for subsequent pages (confirmed against the client's own
   README Pagination section).
2. The post's `UNWIND range(...) AS i CREATE (...)` seeding statement does
   not parse on this server at all (`UNWIND` is not supported --
   confirmed with a live `42000: parse error` on even the simplest
   `UNWIND [1,2,3] AS i RETURN i`). A single `CREATE` with N
   comma-separated node patterns works instead.
"""

import asyncio
import os

from geode_client import open_database


async def stream_large_result() -> None:
    dsn = (
        f"quic://{os.environ['GEODE_HOST']}:{os.environ['GEODE_PORT']}"
        f"?insecure_tls_skip_verify=true&user={os.environ['GEODE_USER']}&pass={os.environ['GEODE_PASSWORD']}"
    )
    client = open_database(dsn)

    async with client.connection() as conn:
        patterns = ", ".join(
            f"(:Person {{id: {i}, country: 'USA'}})" for i in range(1000)
        )
        await conn.execute(f"CREATE {patterns}")

        page, pager = await conn.query(
            "MATCH (p:Person) WHERE p.country = 'USA' RETURN p LIMIT 1000",
            page_size=100,
        )
        count = len(page.rows)
        pages = 1
        async for next_page in pager():
            count += len(next_page.rows)
            pages += 1
        print(f"streamed {count} rows across {pages} page(s)")


if __name__ == "__main__":
    asyncio.run(stream_large_result())
