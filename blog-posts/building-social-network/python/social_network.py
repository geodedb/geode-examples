"""Validates the "Building a Social Network with Geode" post's Python
`SocialNetwork` class ("Step 5: Application Code" -> "Python Example").

The post's own class body is reproduced here essentially verbatim --
every method executes the exact same GQL with the exact same parameter
binding as the post. The ONE thing changed is authentication, and this
is the headline finding for this project (see ../FINDINGS.md): the
post's application code has ZERO authentication anywhere. Its `__init__`
takes a bare `dsn: str` and its `main()` example calls
`SocialNetwork("quic://localhost:3141")` with no credentials at all. A
reader who copies that verbatim gets an immediate `AuthError:
Authentication failed: Authentication required` on the very first
`async with self.client.connection() as conn:` -- confirmed live here
and independently in Task 3's `why-quic-matters` project.

The confirmed-working fix (same as every other Python example in this
repo): embed credentials in the DSN's query string and let
`Connection.connect()`'s own implicit HELLO handshake authenticate.
`geode_client.AuthClient` is NOT used here -- it is dead code: its
methods reference `self.conn._lock` / `_write_json` / `_read_json`,
none of which exist on the real `Connection` class (confirmed by
reading the source and by live reproduction in Task 3). Do not add an
`AuthClient` call to this file.

Second, separate fix (see ../FINDINGS.md section on "entity map
projection"): `get_feed` and `get_recommendations` originally used the
post's `RETURN post { .*, computed: ... } AS alias` entity-map-projection
syntax (with `.*` spread). That syntax does not parse at all in this
GQL dialect -- confirmed live:
`Error: expected identifier or keyword, got 'star' at line N col M`.
Explicit key:value pairs inside the same `entity { ... }` braces also
fail (`expected token 'r_brace', got 'identifier'`) -- the entity-brace
projection form itself isn't supported, not just the `.*` spread inside
it. The working equivalent is a **bare map literal**, not prefixed by
the entity variable: `RETURN {key: entity.prop, ...} AS alias`. Both
methods below use that form.

Third, related finding (this one doesn't show up in the final code
below, because the feature it applies to -- `common_groups`/`score` --
was ultimately dropped entirely; see the fifth point): the post's
`get_recommendations` query has a `WITH me, suggestion, count(friend)
AS mutual_count` clause immediately followed by `OPTIONAL MATCH (...)`.
That combination does not parse -- confirmed live: `Error: expected
token 'RETURN', got 'OPTIONAL' at line N col M`, and confirmed general
(not specific to this query) with a minimal repro (`MATCH (u:User)
WITH u, count(u) AS c OPTIONAL MATCH (u)-[:POSTED]->(p) RETURN ...`
fails identically; the same query with a plain `MATCH` instead of
`OPTIONAL MATCH` after `WITH` succeeds). This GQL dialect does not
allow `OPTIONAL MATCH` as the clause immediately following `WITH`. An
initial fix moved the `OPTIONAL MATCH` after the `WHERE` instead
(dropping the `WITH`) -- but see the fifth point below for why the
`count(DISTINCT ...)` that fix depended on doesn't actually work
either, which is why `common_groups`/`score` are dropped from this
file's `get_recommendations` rather than kept via that fix.

Fourth, the most severe fix, and the reason `get_feed` and
`get_recommendations` look structurally different from the post's
version rather than just auth-patched: **consecutive top-level `MATCH`
clauses that re-reference a variable already bound by an earlier `MATCH`
clause silently ignore that binding.** The post writes exactly this
shape everywhere -- e.g. `get_recommendations`:
`MATCH (me:User {username: $u})-[:FRIENDS_WITH]-(friend)` then, as a
SEPARATE clause, `MATCH (friend)-[:FRIENDS_WITH]-(suggestion)`.
Confirmed live and minimized: `MATCH (me:User {username:"alice"})
MATCH (me)-[:FRIENDS_WITH]-(friend) RETURN friend.username` returns
every node in the entire graph that has ANY `FRIENDS_WITH` edge to
ANYONE -- not just alice's real one friend -- while the semantically
identical **single-clause** form,
`MATCH (me:User {username:"alice"})-[:FRIENDS_WITH]-(friend) RETURN
friend.username`, correctly returns only alice's real friend. The fix,
applied throughout this file: express each traversal as **one single
MATCH clause per connected path** (`MATCH
(me:User {...})-[:FRIENDS_WITH]-(friend)-[:FRIENDS_WITH]-(suggestion)`
in one clause, not two chained ones). `OPTIONAL MATCH` referencing a
variable from the single preceding `MATCH` clause is unaffected by this
bug -- confirmed separately -- so it's only *plain* `MATCH` chains that
need collapsing.

A related, narrower version of the same class of bug: a variable-length
relationship (`*0..1`) chained with a further fixed hop in the *same*
clause (`(me)-[:FRIENDS_WITH*0..1]-(friend)-[:POSTED]->(post)`) also
leaks unrelated nodes into `friend`/`post`, even though it's
syntactically one MATCH clause -- apparently decomposed internally the
same broken way. The `*0..1` segment alone (no further hop chained onto
it) is scoped correctly. `get_feed` below avoids the combination by
using a fixed `-[:FRIENDS_WITH]-` hop (friends' posts only, dropping
the post's "include my own posts via the 0-length hop" behavior) --
confirmed correctly scoped this way.

Also note: node-identity comparison (`me <> suggestion`, as the post
writes it) does not work either -- confirmed live, rows where
`suggestion` is literally the same node as `me` are NOT filtered out by
`WHERE ... AND me <> suggestion`. Comparing a property instead
(`me.username <> suggestion.username`) works correctly and is used
below. `add_friend`'s `MATCH (u1:User {username: $user1}) MATCH
(u2:User {username: $user2})` is NOT affected by any of the above --
each clause does an independent property lookup with no variable
re-referenced as a traversal anchor from a prior clause, which is a
different shape than the buggy one; this was checked specifically
because it's structurally the closest of this file's queries to the
buggy pattern.

Fifth, and independent of everything above: **`count(DISTINCT expr)`
does not work at all -- it always evaluates to `null`, for every
expression type tried (a node variable, a node's string property).**
Confirmed minimally: `MATCH (me:User {username:"x"})-[:FRIENDS_WITH]-(f)
RETURN count(DISTINCT f) AS cnt` -> `{"cnt": null}`, while the identical
query with plain `count(f)` (no `DISTINCT`) correctly returns `2`.
`collect(DISTINCT expr)` doesn't even parse (`expected token 'r_paren',
got 'identifier'`) -- `DISTINCT` inside an aggregate function is only
syntactically accepted by `count()`, and semantically broken there.
This file works around it two ways: (1) `get_recommendations` traverses
`-[:FRIENDS_WITH]->` in ONE direction only (not the post's undirected
`-[:FRIENDS_WITH]-`) -- since `add_friend` always creates both directed
edges for a friendship, one-directional traversal naturally visits each
real friendship exactly once, making plain non-distinct `count(friend)`
correct without needing `DISTINCT` to dedupe the bidirectional storage.
(2) `get_feed`/`get_recommendations` both drop the post's
`like_count`/`comment_count`/`common_groups`/`score` fields entirely,
since those need `count(DISTINCT ...)` to dedupe an `OPTIONAL MATCH`
cross-join and there is no working substitute for that specific
combination found during this task. `mutual_friends` (the field the
post's own pytest test actually asserts on) is unaffected and correct.

Sixth: the post's `.as_object` usage (`row["field"].as_object`, then
indexing the result like a plain dict: `rec['display_name']`) is itself
wrong for the real client library. `Value.as_object` returns
`Dict[str, Value]` -- the values are still `Value`-wrapped, not plain
Python `str`/`int`/etc. Confirmed live: `recs[0]["username"] ==
"charlie"` fails even when the data is correct, because
`recs[0]["username"]` is a `Value(STRING: 'charlie')`, not the string
`"charlie"` (`Value` has no `__eq__` against plain Python types). The
real `geode_client.Value` class has a *separate* property,
`.raw_value`, that recursively unwraps a `Value` (including nested
object/array values) into plain Python types. This file uses
`.raw_value` instead of `.as_object` for exactly that reason; the
post's own pytest assertions (`recs[0]["username"] ==
"charlie"`) only pass with `.raw_value`.

See ../FINDINGS.md for the full, minimized reproductions of all of the
above.
"""

from __future__ import annotations

import asyncio
import os

from geode_client import open_database


def build_dsn(host: str, port: str, user: str, password: str) -> str:
    """Build a DSN with credentials embedded in the query string -- the
    only auth pattern confirmed to work against the real server/client.
    """
    return (
        f"quic://{host}:{port}"
        f"?insecure_tls_skip_verify=true&user={user}&pass={password}"
    )


class SocialNetwork:
    def __init__(self, dsn: str):
        # dsn must already carry ?user=...&pass=...; see build_dsn() above.
        self.client = open_database(dsn)

    async def create_user(
        self, username: str, email: str, display_name: str, password_hash: str
    ):
        """Create a new user"""
        async with self.client.connection() as conn:
            await conn.execute(
                """
                CREATE (u:User {
                  username: $username,
                  email: $email,
                  display_name: $display_name,
                  password_hash: $password_hash,
                  created_at: timestamp()
                })
                """,
                {
                    "username": username,
                    "email": email,
                    "display_name": display_name,
                    "password_hash": password_hash,
                },
            )

    async def create_post(self, username: str, content: str, visibility: str = "public"):
        """Create a new post"""
        async with self.client.connection() as conn:
            await conn.execute(
                """
                MATCH (u:User {username: $username})
                CREATE (u)-[:POSTED {timestamp: timestamp()}]->(p:Post {
                  content: $content,
                  visibility: $visibility,
                  created_at: timestamp()
                })
                """,
                {
                    "username": username,
                    "content": content,
                    "visibility": visibility,
                },
            )

    async def add_friend(self, user1: str, user2: str):
        """Create bidirectional friendship inside a transaction"""
        async with self.client.connection() as conn:
            await conn.begin()
            try:
                await conn.execute(
                    """
                    MATCH (u1:User {username: $user1})
                    MATCH (u2:User {username: $user2})
                    CREATE (u1)-[:FRIENDS_WITH {since: timestamp()}]->(u2)
                    CREATE (u2)-[:FRIENDS_WITH {since: timestamp()}]->(u1)
                    """,
                    {"user1": user1, "user2": user2},
                )
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise

    async def get_feed(self, username: str, limit: int = 50):
        """Get activity feed for user (friends' posts -- see the module
        docstring for why the post's own "include my own posts via
        `*0..1`" behavior is dropped, and why this traverses
        `-[:FRIENDS_WITH]->` in one direction only and drops the
        `like_count`/`comment_count` engagement fields the post's
        version computes with `count(DISTINCT ...)`).
        """
        async with self.client.connection() as conn:
            page, _ = await conn.query(
                """
                MATCH (me:User {username: $username})-[:FRIENDS_WITH]->(friend)-[posted:POSTED]->(post:Post)
                WHERE post.visibility IN ["public", "friends"]

                RETURN {
                  content: post.content,
                  visibility: post.visibility,
                  created_at: post.created_at,
                  author: friend.username,
                  author_name: friend.display_name
                } AS feed_item

                ORDER BY posted.timestamp DESC
                LIMIT $limit
                """,
                {"username": username, "limit": limit},
            )
            return [row["feed_item"].raw_value for row in page.rows]

    async def get_recommendations(self, username: str, limit: int = 10):
        """Get friend recommendations (mutual-friend count only -- see the
        module docstring for why the post's `common_groups`/`score`
        fields, which need `count(DISTINCT ...)`, are dropped).
        """
        async with self.client.connection() as conn:
            page, _ = await conn.query(
                """
                MATCH (me:User {username: $username})-[:FRIENDS_WITH]->(friend)-[:FRIENDS_WITH]->(suggestion)
                WHERE me.username <> suggestion.username
                  AND NOT (me)-[:FRIENDS_WITH]->(suggestion)

                RETURN {
                  username: suggestion.username,
                  display_name: suggestion.display_name,
                  mutual_friends: count(friend)
                } AS recommendation

                LIMIT $limit
                """,
                {"username": username, "limit": limit},
            )
            return [row["recommendation"].raw_value for row in page.rows]


async def main():
    dsn = build_dsn(
        os.environ["GEODE_HOST"],
        os.environ["GEODE_PORT"],
        os.environ["GEODE_USER"],
        os.environ["GEODE_PASSWORD"],
    )
    network = SocialNetwork(dsn)

    await network.create_user(
        "smoketest_alice", "smoketest_alice@example.com", "Alice Test", "hash123"
    )
    await network.create_user(
        "smoketest_bob", "smoketest_bob@example.com", "Bob Test", "hash456"
    )
    await network.create_post("smoketest_alice", "Hello, Geode world!", "public")
    await network.add_friend("smoketest_alice", "smoketest_bob")

    feed = await network.get_feed("smoketest_alice")
    recs = await network.get_recommendations("smoketest_alice")
    print(
        f"OK: create_user/create_post/add_friend/get_feed/get_recommendations "
        f"all ran, {len(feed)} feed item(s), {len(recs)} recommendation(s)"
    )


if __name__ == "__main__":
    asyncio.run(main())
