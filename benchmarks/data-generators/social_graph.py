#!/usr/bin/env python3
"""
Social Graph Data Generator

Generates realistic social network graph data for benchmarking.
CANARY: REQ=REQ-DATA-SOCIAL-001; FEATURE="SocialGraphGen"; ASPECT=Benchmarks; STATUS=TESTED

This generator creates:
- Users with profiles (name, age, location, interests)
- Friendship relationships (bidirectional)
- Follow relationships (directional)
- Posts with content and timestamps
- Likes and comments on posts
"""
import argparse
import json
import random
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional


# Sample data for realistic generation
FIRST_NAMES = [
    "Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry",
    "Ivy", "Jack", "Kate", "Liam", "Maya", "Noah", "Olivia", "Peter",
    "Quinn", "Rachel", "Sam", "Tara", "Uma", "Victor", "Wendy", "Xavier",
    "Yuki", "Zoe", "Aaron", "Beth", "Carl", "Dana"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Anderson", "Taylor", "Thomas",
    "Moore", "Jackson", "Martin", "Lee", "Thompson", "White", "Harris"
]

CITIES = [
    "New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia",
    "San Antonio", "San Diego", "Dallas", "San Jose", "Austin", "Seattle",
    "Denver", "Boston", "Portland", "Atlanta", "Miami", "Minneapolis"
]

INTERESTS = [
    "technology", "sports", "music", "art", "travel", "cooking", "reading",
    "gaming", "photography", "fitness", "movies", "gardening", "fashion",
    "science", "politics", "nature", "meditation", "dancing", "writing"
]

POST_TEMPLATES = [
    "Just had an amazing {thing}!",
    "Anyone else excited about {thing}?",
    "Working on a new {thing} project.",
    "Thoughts on {thing}?",
    "Check out this {thing}!",
    "Learning about {thing} today.",
    "My experience with {thing}:",
]


@dataclass
class GenerationResult:
    """Result of data generation."""
    users_created: int
    friendships_created: int
    follows_created: int
    posts_created: int
    likes_created: int
    comments_created: int
    duration_seconds: float
    errors: int


class SocialGraphGenerator:
    """Generates social graph data for Geode."""

    def __init__(self, use_docker: bool = True, batch_size: int = 100):
        self.use_docker = use_docker
        self.batch_size = batch_size
        self.users: List[str] = []
        self.posts: List[str] = []
        self.errors = 0

    def execute(self, query: str, timeout: float = 30.0) -> bool:
        """Execute a GQL query."""
        try:
            if self.use_docker:
                cmd = ["docker", "compose", "exec", "-T", "geode", "geode", "shell", "-c", query]
            else:
                cmd = ["geode", "shell", "-c", query]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0:
                self.errors += 1
                return False
            return True
        except Exception:
            self.errors += 1
            return False

    def generate_user(self, user_id: int) -> str:
        """Generate a user node creation query."""
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        age = random.randint(18, 75)
        city = random.choice(CITIES)
        user_interests = random.sample(INTERESTS, k=random.randint(2, 5))
        join_date = datetime.now() - timedelta(days=random.randint(1, 1000))

        user_uuid = f"user_{user_id}"
        self.users.append(user_uuid)

        return f"""
        CREATE (u:User:Person {{
            id: '{user_uuid}',
            first_name: '{first}',
            last_name: '{last}',
            name: '{first} {last}',
            age: {age},
            city: '{city}',
            interests: {json.dumps(user_interests)},
            join_date: date('{join_date.strftime('%Y-%m-%d')}'),
            email: '{first.lower()}.{last.lower()}@example.com',
            verified: {str(random.random() > 0.3).lower()}
        }})
        """

    def generate_friendship(self, user1: str, user2: str) -> str:
        """Generate a friendship relationship (bidirectional in practice)."""
        since = datetime.now() - timedelta(days=random.randint(1, 500))
        return f"""
        MATCH (a:User {{id: '{user1}'}}), (b:User {{id: '{user2}'}})
        CREATE (a)-[:FRIENDS_WITH {{since: date('{since.strftime('%Y-%m-%d')}')}}]->(b)
        """

    def generate_follow(self, follower: str, followee: str) -> str:
        """Generate a follow relationship (directional)."""
        since = datetime.now() - timedelta(days=random.randint(1, 500))
        return f"""
        MATCH (a:User {{id: '{follower}'}}), (b:User {{id: '{followee}'}})
        CREATE (a)-[:FOLLOWS {{since: date('{since.strftime('%Y-%m-%d')}')}}]->(b)
        """

    def generate_post(self, author: str, post_id: int) -> str:
        """Generate a post node."""
        template = random.choice(POST_TEMPLATES)
        thing = random.choice(INTERESTS)
        content = template.format(thing=thing)
        created = datetime.now() - timedelta(days=random.randint(0, 100))

        post_uuid = f"post_{post_id}"
        self.posts.append(post_uuid)

        return f"""
        MATCH (u:User {{id: '{author}'}})
        CREATE (p:Post {{
            id: '{post_uuid}',
            content: '{content}',
            created_at: datetime('{created.isoformat()}'),
            likes_count: 0,
            comments_count: 0
        }})
        CREATE (u)-[:AUTHORED]->(p)
        """

    def generate_like(self, user: str, post: str) -> str:
        """Generate a like relationship."""
        return f"""
        MATCH (u:User {{id: '{user}'}}), (p:Post {{id: '{post}'}})
        CREATE (u)-[:LIKES {{created_at: datetime()}}]->(p)
        """

    def generate_comment(self, user: str, post: str, comment_id: int) -> str:
        """Generate a comment on a post."""
        comments = [
            "Great post!", "Interesting!", "Thanks for sharing!",
            "I agree!", "Nice one!", "Love this!", "So true!"
        ]
        return f"""
        MATCH (u:User {{id: '{user}'}}), (p:Post {{id: '{post}'}})
        CREATE (c:Comment {{
            id: 'comment_{comment_id}',
            content: '{random.choice(comments)}',
            created_at: datetime()
        }})
        CREATE (u)-[:WROTE]->(c)
        CREATE (c)-[:ON_POST]->(p)
        """

    def generate(
        self,
        num_users: int,
        avg_friends_per_user: int = 10,
        avg_follows_per_user: int = 20,
        avg_posts_per_user: int = 5,
        avg_likes_per_post: int = 10,
        avg_comments_per_post: int = 3
    ) -> GenerationResult:
        """Generate a complete social graph."""
        start_time = time.monotonic()

        print(f"Generating social graph with {num_users:,} users...")

        # Phase 1: Create users
        print("  Phase 1: Creating users...")
        users_created = 0
        for i in range(num_users):
            query = self.generate_user(i)
            if self.execute(query):
                users_created += 1
            if (i + 1) % 100 == 0:
                print(f"    Progress: {i + 1}/{num_users} users")

        # Phase 2: Create friendships
        print("  Phase 2: Creating friendships...")
        friendships_created = 0
        total_friendships = num_users * avg_friends_per_user // 2
        for _ in range(total_friendships):
            user1, user2 = random.sample(self.users, 2)
            query = self.generate_friendship(user1, user2)
            if self.execute(query):
                friendships_created += 1

        print(f"    Created {friendships_created} friendships")

        # Phase 3: Create follows
        print("  Phase 3: Creating follows...")
        follows_created = 0
        total_follows = num_users * avg_follows_per_user
        for _ in range(total_follows):
            follower, followee = random.sample(self.users, 2)
            query = self.generate_follow(follower, followee)
            if self.execute(query):
                follows_created += 1

        print(f"    Created {follows_created} follows")

        # Phase 4: Create posts
        print("  Phase 4: Creating posts...")
        posts_created = 0
        post_id = 0
        for user in self.users:
            num_posts = random.randint(0, avg_posts_per_user * 2)
            for _ in range(num_posts):
                query = self.generate_post(user, post_id)
                if self.execute(query):
                    posts_created += 1
                post_id += 1

        print(f"    Created {posts_created} posts")

        # Phase 5: Create likes
        print("  Phase 5: Creating likes...")
        likes_created = 0
        if self.posts:
            for post in self.posts:
                num_likes = random.randint(0, avg_likes_per_post * 2)
                likers = random.sample(self.users, min(num_likes, len(self.users)))
                for user in likers:
                    query = self.generate_like(user, post)
                    if self.execute(query):
                        likes_created += 1

        print(f"    Created {likes_created} likes")

        # Phase 6: Create comments
        print("  Phase 6: Creating comments...")
        comments_created = 0
        comment_id = 0
        if self.posts:
            for post in self.posts:
                num_comments = random.randint(0, avg_comments_per_post * 2)
                commenters = random.sample(self.users, min(num_comments, len(self.users)))
                for user in commenters:
                    query = self.generate_comment(user, post, comment_id)
                    if self.execute(query):
                        comments_created += 1
                    comment_id += 1

        print(f"    Created {comments_created} comments")

        duration = time.monotonic() - start_time

        return GenerationResult(
            users_created=users_created,
            friendships_created=friendships_created,
            follows_created=follows_created,
            posts_created=posts_created,
            likes_created=likes_created,
            comments_created=comments_created,
            duration_seconds=duration,
            errors=self.errors
        )


def print_result(result: GenerationResult):
    """Print generation results."""
    print("\n" + "=" * 50)
    print("SOCIAL GRAPH GENERATION COMPLETE")
    print("=" * 50)
    print(f"Duration: {result.duration_seconds:.2f}s")
    print()
    print("NODES CREATED:")
    print(f"  Users:      {result.users_created:,}")
    print(f"  Posts:      {result.posts_created:,}")
    print()
    print("RELATIONSHIPS CREATED:")
    print(f"  Friendships: {result.friendships_created:,}")
    print(f"  Follows:     {result.follows_created:,}")
    print(f"  Likes:       {result.likes_created:,}")
    print(f"  Comments:    {result.comments_created:,}")
    print()
    print(f"Errors: {result.errors}")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="Generate social graph data for Geode")
    parser.add_argument("--users", "-u", type=int, default=100, help="Number of users (default: 100)")
    parser.add_argument("--friends", "-f", type=int, default=10, help="Avg friends per user (default: 10)")
    parser.add_argument("--follows", type=int, default=20, help="Avg follows per user (default: 20)")
    parser.add_argument("--posts", "-p", type=int, default=5, help="Avg posts per user (default: 5)")
    parser.add_argument("--likes", "-l", type=int, default=10, help="Avg likes per post (default: 10)")
    parser.add_argument("--comments", "-c", type=int, default=3, help="Avg comments per post (default: 3)")
    parser.add_argument("--no-docker", action="store_true", help="Don't use docker compose")

    args = parser.parse_args()

    generator = SocialGraphGenerator(use_docker=not args.no_docker)
    result = generator.generate(
        num_users=args.users,
        avg_friends_per_user=args.friends,
        avg_follows_per_user=args.follows,
        avg_posts_per_user=args.posts,
        avg_likes_per_post=args.likes,
        avg_comments_per_post=args.comments
    )

    print_result(result)
    sys.exit(0 if result.errors == 0 else 1)


if __name__ == "__main__":
    main()
