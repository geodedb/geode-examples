"""Validates the "Building a Social Network with Geode" post's own pytest
suite ("Testing" section), run for real against a live container.

Three changes from the post's original tests, all documented in
../FINDINGS.md:

1. Auth: the fixture builds a DSN with embedded credentials (see
   social_network.py's build_dsn()) instead of the post's bare
   `SocialNetwork("quic://localhost:3141")`.

2. Cleanup: the post's fixture does
   `await conn.execute("MATCH (n) DETACH DELETE n")` as teardown. That
   wipes every node and relationship in the ENTIRE graph -- not just
   what this test created. Against a shared/real database (this project
   runs against the same `geode-blog-posts` container every other task
   in this repo also writes to) that is actively dangerous: it would
   delete the sample data seeded by sample_data.gql and any data left
   behind by the other three example projects' validation runs. This
   file does NOT do that. Instead every test uses uniquely-prefixed
   usernames and skips whole-graph cleanup entirely.

3. Per-run random suffix: `schema.gql`'s `CREATE UNIQUE INDEX
   user_username_unique ON User(username)` does NOT actually enforce
   uniqueness -- confirmed live: two `CREATE (:User {username: "x", ...})`
   statements with the identical username both succeeded with zero
   error, producing two separate nodes with the same username (see
   ../FINDINGS.md). Combined with point 2 above (no cleanup, ever),
   naively fixed usernames like `pytest_alice2` would accumulate a
   fresh duplicate `User` node -- and therefore inflated match/friend
   counts -- on every single test run, eventually breaking the exact
   `len(recs) == 1` assertion below. Each test run generates its own
   random suffix so usernames are unique *per run*, keeping the
   assertions deterministic regardless of that server-side bug.
"""

import os
import uuid

import pytest

from social_network import SocialNetwork, build_dsn

# Unique per test-process run so repeated `pytest` invocations never
# collide with each other's data -- see point 3 in the module docstring.
RUN_ID = uuid.uuid4().hex[:8]


@pytest.fixture
def network():
    dsn = build_dsn(
        os.environ["GEODE_HOST"],
        os.environ["GEODE_PORT"],
        os.environ["GEODE_USER"],
        os.environ["GEODE_PASSWORD"],
    )
    return SocialNetwork(dsn)


@pytest.mark.asyncio
async def test_create_user(network):
    username = f"pytest_test_{RUN_ID}"
    await network.create_user(username, f"{username}@example.com", "Test User", "hash")

    async with network.client.connection() as conn:
        page, _ = await conn.query(
            "MATCH (u:User {username: $username}) RETURN u",
            {"username": username},
        )
    assert len(page.rows) == 1


@pytest.mark.asyncio
async def test_friend_recommendations(network):
    # Create test data -- uniquely prefixed/suffixed so this doesn't
    # collide with sample_data.gql's alice/bob/charlie, with any other
    # test in this file, or with a prior run of this same test (see the
    # module docstring's point 3).
    alice = f"pytest_alice2_{RUN_ID}"
    bob = f"pytest_bob2_{RUN_ID}"
    charlie = f"pytest_charlie2_{RUN_ID}"

    await network.create_user(alice, f"{alice}@example.com", "Alice", "hash1")
    await network.create_user(bob, f"{bob}@example.com", "Bob", "hash2")
    await network.create_user(charlie, f"{charlie}@example.com", "Charlie", "hash3")

    await network.add_friend(alice, bob)
    await network.add_friend(bob, charlie)

    # Get recommendations for alice
    recs = await network.get_recommendations(alice)

    # Should recommend charlie
    assert len(recs) == 1
    assert recs[0]["username"] == charlie
    assert recs[0]["mutual_friends"] == 1
