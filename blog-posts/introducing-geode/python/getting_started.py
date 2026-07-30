"""Runs the two operations from the "Introducing Geode" blog post's Getting
Started section, using the async Python client shown in the post's "Native
Language Support" section.

The post's own snippet never authenticates at all. Against a real server
that requires auth on every connection, that fails. See ../FINDINGS.md for
the full story; this file uses the corrected DSN-param auth flow.
"""

import asyncio
import os

from geode_client import open_database


async def main() -> None:
    # NOTE: the Python client's DSN option is `skip_verify` (0/1), not
    # `insecure_tls_skip_verify` like the Go/Node/Rust/Zig clients -- see
    # ../FINDINGS.md. `user`/`pass` DSN params authenticate the connection
    # up front, so the separate AuthClient.login() call the post's own
    # snippet never mentions is not needed.
    dsn = (
        f"quic://{os.environ['GEODE_HOST']}:{os.environ['GEODE_PORT']}"
        f"?skip_verify=1&user={os.environ['GEODE_USER']}&pass={os.environ['GEODE_PASSWORD']}"
    )
    client = open_database(dsn)

    async with client.connection() as conn:
        await conn.execute("CREATE (:Person {name: 'Alice', age: 30})")
        page, _ = await conn.query("MATCH (p:Person) RETURN p")
        # The post's "Native Language Support" snippet iterates `page.rows`
        # directly (its distinctive feature: results are async-iterator
        # friendly rather than buffered into a generic Row map) -- mirrored
        # here rather than just taking len().
        for row in page.rows:
            print(row)
        print(f"OK: {len(page.rows)} Person node(s) returned")


if __name__ == "__main__":
    asyncio.run(main())
