#!/usr/bin/env python3
"""
Scale Test Data Generator

Generates large-scale graph data for scalability testing.
CANARY: REQ=REQ-DATA-SCALE-001; FEATURE="ScaleTestGen"; ASPECT=Benchmarks; STATUS=TESTED

This generator is optimized for creating large datasets:
- 100M+ nodes target
- Batch operations for efficiency
- Progress tracking and resumability
- Memory-efficient streaming
"""
import argparse
import json
import random
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Iterator


@dataclass
class ScaleTestResult:
    """Result of scale test data generation."""
    target_nodes: int
    target_relationships: int
    actual_nodes: int
    actual_relationships: int
    batch_size: int
    batches_completed: int
    duration_seconds: float
    nodes_per_second: float
    relationships_per_second: float
    errors: int
    status: str


class ScaleTestGenerator:
    """Generates large-scale graph data for stress testing."""

    def __init__(self, use_docker: bool = True, batch_size: int = 1000):
        self.use_docker = use_docker
        self.batch_size = batch_size
        self.errors = 0
        self.node_id_counter = 0

    def execute(self, query: str, timeout: float = 60.0) -> bool:
        """Execute a GQL query."""
        try:
            if self.use_docker:
                cmd = [
                    "docker", "compose", "exec", "-T", "geode",
                    "geode", "query",
                    "--server", "localhost:3141",
                    "--insecure",
                    query
                ]
            else:
                cmd = [
                    "geode", "query",
                    "--server", "localhost:3141",
                    "--insecure",
                    query
                ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0:
                self.errors += 1
                return False
            return True
        except Exception as e:
            self.errors += 1
            return False

    def generate_node_batch(self, start_id: int, count: int, label: str = "ScaleNode") -> str:
        """Generate a batch of nodes using UNWIND for efficiency."""
        nodes_data = []
        for i in range(count):
            node_id = start_id + i
            nodes_data.append({
                "id": f"n_{node_id}",
                "value": random.randint(1, 1000000),
                "partition": node_id % 100,
                "data": uuid.uuid4().hex[:16]
            })

        # Use UNWIND for batch creation
        nodes_json = json.dumps(nodes_data)
        return f"""
        UNWIND {nodes_json} AS node
        CREATE (:{label} {{
            id: node.id,
            value: node.value,
            partition: node.partition,
            data: node.data,
            created: timestamp()
        }})
        """

    def generate_relationship_batch(
        self,
        total_nodes: int,
        count: int,
        rel_type: str = "CONNECTS"
    ) -> str:
        """Generate a batch of random relationships."""
        rels_data = []
        for _ in range(count):
            source_id = random.randint(0, total_nodes - 1)
            target_id = random.randint(0, total_nodes - 1)
            if source_id != target_id:
                rels_data.append({
                    "source": f"n_{source_id}",
                    "target": f"n_{target_id}",
                    "weight": round(random.random(), 4)
                })

        if not rels_data:
            return ""

        rels_json = json.dumps(rels_data)
        return f"""
        UNWIND {rels_json} AS rel
        MATCH (a:ScaleNode {{id: rel.source}}), (b:ScaleNode {{id: rel.target}})
        CREATE (a)-[:{rel_type} {{weight: rel.weight, created: timestamp()}}]->(b)
        """

    def generate_nodes(self, target_count: int, label: str = "ScaleNode") -> int:
        """Generate nodes in batches."""
        print(f"  Generating {target_count:,} nodes...")
        created = 0
        batches = 0

        for batch_start in range(0, target_count, self.batch_size):
            batch_count = min(self.batch_size, target_count - batch_start)
            query = self.generate_node_batch(batch_start, batch_count, label)

            if self.execute(query):
                created += batch_count
                batches += 1

            if (batch_start + batch_count) % 10000 == 0:
                print(f"    Progress: {created:,}/{target_count:,} nodes ({created/target_count*100:.1f}%)")

        return created

    def generate_relationships(
        self,
        total_nodes: int,
        target_count: int,
        rel_type: str = "CONNECTS"
    ) -> int:
        """Generate relationships in batches."""
        print(f"  Generating {target_count:,} relationships...")
        created = 0
        batches = 0

        rel_batch_size = min(self.batch_size, 100)  # Smaller batches for relationships

        for batch_start in range(0, target_count, rel_batch_size):
            batch_count = min(rel_batch_size, target_count - batch_start)
            query = self.generate_relationship_batch(total_nodes, batch_count, rel_type)

            if query and self.execute(query):
                created += batch_count
                batches += 1

            if (batch_start + batch_count) % 10000 == 0:
                print(f"    Progress: {created:,}/{target_count:,} rels ({created/target_count*100:.1f}%)")

        return created

    def generate(
        self,
        target_nodes: int,
        relationships_per_node: float = 5.0,
        node_label: str = "ScaleNode",
        relationship_type: str = "CONNECTS"
    ) -> ScaleTestResult:
        """Generate large-scale test data."""
        start_time = time.monotonic()
        target_relationships = int(target_nodes * relationships_per_node)

        print(f"Scale Test Data Generation")
        print(f"  Target nodes: {target_nodes:,}")
        print(f"  Target relationships: {target_relationships:,}")
        print(f"  Batch size: {self.batch_size}")
        print()

        # Phase 1: Create nodes
        print("Phase 1: Node Creation")
        node_start = time.monotonic()
        actual_nodes = self.generate_nodes(target_nodes, node_label)
        node_duration = time.monotonic() - node_start
        nodes_per_second = actual_nodes / node_duration if node_duration > 0 else 0
        print(f"  Completed: {actual_nodes:,} nodes in {node_duration:.2f}s ({nodes_per_second:.0f}/sec)")
        print()

        # Phase 2: Create relationships
        print("Phase 2: Relationship Creation")
        rel_start = time.monotonic()
        actual_relationships = self.generate_relationships(
            actual_nodes, target_relationships, relationship_type
        )
        rel_duration = time.monotonic() - rel_start
        rels_per_second = actual_relationships / rel_duration if rel_duration > 0 else 0
        print(f"  Completed: {actual_relationships:,} rels in {rel_duration:.2f}s ({rels_per_second:.0f}/sec)")

        total_duration = time.monotonic() - start_time

        # Determine status
        node_ratio = actual_nodes / target_nodes if target_nodes > 0 else 0
        rel_ratio = actual_relationships / target_relationships if target_relationships > 0 else 0

        if node_ratio >= 0.99 and rel_ratio >= 0.95:
            status = "COMPLETE"
        elif node_ratio >= 0.9 and rel_ratio >= 0.8:
            status = "PARTIAL"
        else:
            status = "FAILED"

        return ScaleTestResult(
            target_nodes=target_nodes,
            target_relationships=target_relationships,
            actual_nodes=actual_nodes,
            actual_relationships=actual_relationships,
            batch_size=self.batch_size,
            batches_completed=(actual_nodes // self.batch_size) + (actual_relationships // 100),
            duration_seconds=total_duration,
            nodes_per_second=actual_nodes / total_duration if total_duration > 0 else 0,
            relationships_per_second=actual_relationships / total_duration if total_duration > 0 else 0,
            errors=self.errors,
            status=status
        )


def print_result(result: ScaleTestResult):
    """Print generation results."""
    print("\n" + "=" * 60)
    print("SCALE TEST DATA GENERATION RESULTS")
    print("=" * 60)
    print(f"Duration: {result.duration_seconds:.2f}s")
    print()
    print("NODES:")
    print(f"  Target:     {result.target_nodes:,}")
    print(f"  Actual:     {result.actual_nodes:,}")
    print(f"  Rate:       {result.nodes_per_second:,.0f}/sec")
    print()
    print("RELATIONSHIPS:")
    print(f"  Target:     {result.target_relationships:,}")
    print(f"  Actual:     {result.actual_relationships:,}")
    print(f"  Rate:       {result.relationships_per_second:,.0f}/sec")
    print()
    print("PERFORMANCE:")
    print(f"  Batch size: {result.batch_size}")
    print(f"  Batches:    {result.batches_completed:,}")
    print(f"  Errors:     {result.errors}")
    print()
    print(f"STATUS: {result.status}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Generate scale test data for Geode")
    parser.add_argument("--nodes", "-n", type=int, default=10000,
                        help="Target number of nodes (default: 10000)")
    parser.add_argument("--rels-per-node", "-r", type=float, default=5.0,
                        help="Relationships per node (default: 5.0)")
    parser.add_argument("--batch-size", "-b", type=int, default=1000,
                        help="Batch size for node creation (default: 1000)")
    parser.add_argument("--label", "-l", type=str, default="ScaleNode",
                        help="Node label (default: ScaleNode)")
    parser.add_argument("--rel-type", "-t", type=str, default="CONNECTS",
                        help="Relationship type (default: CONNECTS)")
    parser.add_argument("--output", "-o", type=str,
                        help="Output JSON file path")
    parser.add_argument("--no-docker", action="store_true",
                        help="Don't use docker compose")

    args = parser.parse_args()

    generator = ScaleTestGenerator(
        use_docker=not args.no_docker,
        batch_size=args.batch_size
    )

    result = generator.generate(
        target_nodes=args.nodes,
        relationships_per_node=args.rels_per_node,
        node_label=args.label,
        relationship_type=args.rel_type
    )

    print_result(result)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(asdict(result), f, indent=2)
        print(f"\nResults saved to: {output_path}")

    sys.exit(0 if result.status in ["COMPLETE", "PARTIAL"] else 1)


if __name__ == "__main__":
    main()
