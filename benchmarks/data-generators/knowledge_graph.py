#!/usr/bin/env python3
"""
Knowledge Graph Data Generator

Generates realistic knowledge graph data for benchmarking.
CANARY: REQ=REQ-DATA-KNOWLEDGE-001; FEATURE="KnowledgeGraphGen"; ASPECT=Benchmarks; STATUS=TESTED

This generator creates:
- Entities (people, organizations, places, concepts)
- Various relationship types (works_at, located_in, related_to, etc.)
- Properties and attributes
- Hierarchical structures
"""
import argparse
import json
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional


# Domain data for knowledge graph generation
ENTITY_TYPES = {
    "Person": {
        "properties": ["name", "birth_date", "nationality", "occupation"],
        "count_weight": 3
    },
    "Organization": {
        "properties": ["name", "founded", "industry", "headquarters"],
        "count_weight": 2
    },
    "Place": {
        "properties": ["name", "country", "population", "coordinates"],
        "count_weight": 2
    },
    "Concept": {
        "properties": ["name", "category", "description"],
        "count_weight": 2
    },
    "Event": {
        "properties": ["name", "date", "location", "description"],
        "count_weight": 1
    },
    "Product": {
        "properties": ["name", "category", "manufacturer", "release_date"],
        "count_weight": 2
    },
    "Technology": {
        "properties": ["name", "category", "year_invented", "inventor"],
        "count_weight": 1
    }
}

RELATIONSHIP_TYPES = [
    ("Person", "WORKS_AT", "Organization"),
    ("Person", "BORN_IN", "Place"),
    ("Person", "LIVES_IN", "Place"),
    ("Person", "KNOWS", "Person"),
    ("Person", "CREATED", "Product"),
    ("Person", "INVENTED", "Technology"),
    ("Organization", "HEADQUARTERED_IN", "Place"),
    ("Organization", "PRODUCES", "Product"),
    ("Organization", "USES", "Technology"),
    ("Place", "LOCATED_IN", "Place"),
    ("Place", "CAPITAL_OF", "Place"),
    ("Concept", "RELATED_TO", "Concept"),
    ("Concept", "PART_OF", "Concept"),
    ("Event", "OCCURRED_IN", "Place"),
    ("Event", "INVOLVED", "Person"),
    ("Product", "USES", "Technology"),
    ("Technology", "SUPERSEDES", "Technology"),
]

# Sample data
PERSON_NAMES = [
    "Albert Einstein", "Marie Curie", "Isaac Newton", "Ada Lovelace",
    "Alan Turing", "Nikola Tesla", "Charles Darwin", "Jane Goodall",
    "Stephen Hawking", "Grace Hopper", "Richard Feynman", "Rosalind Franklin"
]

ORGANIZATION_NAMES = [
    "Acme Corp", "TechGiant Inc", "Global Systems", "Innovation Labs",
    "Research Institute", "University of Science", "Data Systems Ltd",
    "Cloud Solutions", "AI Research Center", "Quantum Computing Institute"
]

PLACE_NAMES = [
    "New York", "London", "Tokyo", "Paris", "Berlin", "Sydney",
    "San Francisco", "Toronto", "Singapore", "Amsterdam", "Stockholm",
    "Munich", "Boston", "Seattle", "Austin", "Tel Aviv"
]

CONCEPT_NAMES = [
    "Artificial Intelligence", "Machine Learning", "Graph Theory",
    "Quantum Computing", "Cryptography", "Distributed Systems",
    "Data Science", "Neural Networks", "Computer Vision", "NLP"
]

PRODUCT_NAMES = [
    "DataProcessor Pro", "GraphEngine 3.0", "QueryOptimizer",
    "VectorDB", "StreamProcessor", "AnalyticsSuite", "MLPipeline"
]

TECHNOLOGY_NAMES = [
    "Graph Database", "QUIC Protocol", "Vector Index", "HNSW Algorithm",
    "B-tree Index", "Raft Consensus", "Merkle Tree", "Bloom Filter"
]


@dataclass
class GenerationResult:
    """Result of data generation."""
    entities_created: Dict[str, int]
    relationships_created: int
    total_nodes: int
    total_relationships: int
    duration_seconds: float
    errors: int


class KnowledgeGraphGenerator:
    """Generates knowledge graph data for Geode."""

    def __init__(self, use_docker: bool = True):
        self.use_docker = use_docker
        self.entities: Dict[str, List[str]] = {et: [] for et in ENTITY_TYPES}
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

    def get_sample_name(self, entity_type: str, index: int) -> str:
        """Get a sample name for an entity type."""
        if entity_type == "Person":
            names = PERSON_NAMES
        elif entity_type == "Organization":
            names = ORGANIZATION_NAMES
        elif entity_type == "Place":
            names = PLACE_NAMES
        elif entity_type == "Concept":
            names = CONCEPT_NAMES
        elif entity_type == "Product":
            names = PRODUCT_NAMES
        elif entity_type == "Technology":
            names = TECHNOLOGY_NAMES
        else:
            names = [f"{entity_type}_{i}" for i in range(100)]

        base_name = names[index % len(names)]
        if index >= len(names):
            return f"{base_name} {index // len(names) + 1}"
        return base_name

    def generate_entity(self, entity_type: str, entity_id: int) -> str:
        """Generate an entity node creation query."""
        props = ENTITY_TYPES[entity_type]["properties"]
        name = self.get_sample_name(entity_type, entity_id)
        uuid = f"{entity_type.lower()}_{entity_id}"

        self.entities[entity_type].append(uuid)

        # Build properties based on entity type
        prop_str = f"id: '{uuid}', name: '{name}'"

        if entity_type == "Person":
            prop_str += f", occupation: '{random.choice(['Scientist', 'Engineer', 'Researcher', 'Professor'])}'"
            prop_str += f", nationality: '{random.choice(['USA', 'UK', 'Germany', 'France', 'Japan'])}'"
        elif entity_type == "Organization":
            prop_str += f", industry: '{random.choice(['Technology', 'Research', 'Education', 'Finance'])}'"
            prop_str += f", founded: {random.randint(1900, 2023)}"
        elif entity_type == "Place":
            prop_str += f", country: '{random.choice(['USA', 'UK', 'Germany', 'France', 'Japan', 'Australia'])}'"
            prop_str += f", population: {random.randint(10000, 10000000)}"
        elif entity_type == "Concept":
            prop_str += f", category: '{random.choice(['Science', 'Technology', 'Mathematics', 'Engineering'])}'"
        elif entity_type == "Product":
            prop_str += f", category: '{random.choice(['Software', 'Database', 'Analytics', 'Infrastructure'])}'"
        elif entity_type == "Technology":
            prop_str += f", year_invented: {random.randint(1950, 2023)}"

        return f"CREATE (:{entity_type} {{{prop_str}}})"

    def generate_relationship(self, source_type: str, rel_type: str, target_type: str) -> Optional[str]:
        """Generate a relationship between entities."""
        if not self.entities[source_type] or not self.entities[target_type]:
            return None

        source = random.choice(self.entities[source_type])
        target = random.choice(self.entities[target_type])

        if source == target:
            return None

        props = ""
        if rel_type in ["WORKS_AT", "LIVES_IN"]:
            props = f", since: {random.randint(2000, 2023)}"
        elif rel_type in ["KNOWS"]:
            props = f", strength: {random.random():.2f}"
        elif rel_type in ["RELATED_TO"]:
            props = f", weight: {random.random():.2f}"

        return f"""
        MATCH (a:{source_type} {{id: '{source}'}}), (b:{target_type} {{id: '{target}'}})
        CREATE (a)-[:{rel_type} {{created: datetime(){props}}}]->(b)
        """

    def generate(
        self,
        num_entities: int,
        relationships_per_entity: int = 3
    ) -> GenerationResult:
        """Generate a complete knowledge graph."""
        start_time = time.monotonic()

        print(f"Generating knowledge graph with ~{num_entities:,} entities...")

        # Calculate entity distribution based on weights
        total_weight = sum(t["count_weight"] for t in ENTITY_TYPES.values())
        entity_counts = {
            et: int(num_entities * data["count_weight"] / total_weight)
            for et, data in ENTITY_TYPES.items()
        }

        # Phase 1: Create entities
        print("  Phase 1: Creating entities...")
        entities_created = {et: 0 for et in ENTITY_TYPES}

        for entity_type, count in entity_counts.items():
            print(f"    Creating {count} {entity_type} entities...")
            for i in range(count):
                query = self.generate_entity(entity_type, i)
                if self.execute(query):
                    entities_created[entity_type] += 1
                if (i + 1) % 100 == 0:
                    print(f"      Progress: {i + 1}/{count}")

        total_nodes = sum(entities_created.values())
        print(f"    Total entities created: {total_nodes}")

        # Phase 2: Create relationships
        print("  Phase 2: Creating relationships...")
        relationships_created = 0
        target_relationships = total_nodes * relationships_per_entity

        for _ in range(target_relationships):
            # Pick a random relationship type
            rel_spec = random.choice(RELATIONSHIP_TYPES)
            source_type, rel_type, target_type = rel_spec

            query = self.generate_relationship(source_type, rel_type, target_type)
            if query and self.execute(query):
                relationships_created += 1

        print(f"    Relationships created: {relationships_created}")

        # Phase 3: Create hierarchical structures (for concepts)
        print("  Phase 3: Creating hierarchical structures...")
        concepts = self.entities.get("Concept", [])
        if len(concepts) > 1:
            # Create a tree-like structure
            for i in range(1, len(concepts)):
                parent_idx = (i - 1) // 2
                query = f"""
                MATCH (child:Concept {{id: '{concepts[i]}'}}),
                      (parent:Concept {{id: '{concepts[parent_idx]}'}})
                CREATE (child)-[:PART_OF]->(parent)
                """
                if self.execute(query):
                    relationships_created += 1

        duration = time.monotonic() - start_time

        return GenerationResult(
            entities_created=entities_created,
            relationships_created=relationships_created,
            total_nodes=total_nodes,
            total_relationships=relationships_created,
            duration_seconds=duration,
            errors=self.errors
        )


def print_result(result: GenerationResult):
    """Print generation results."""
    print("\n" + "=" * 50)
    print("KNOWLEDGE GRAPH GENERATION COMPLETE")
    print("=" * 50)
    print(f"Duration: {result.duration_seconds:.2f}s")
    print()
    print("ENTITIES CREATED:")
    for entity_type, count in result.entities_created.items():
        print(f"  {entity_type}: {count:,}")
    print(f"  Total: {result.total_nodes:,}")
    print()
    print(f"RELATIONSHIPS CREATED: {result.total_relationships:,}")
    print()
    print(f"Errors: {result.errors}")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="Generate knowledge graph data for Geode")
    parser.add_argument("--entities", "-e", type=int, default=100,
                        help="Approximate number of entities (default: 100)")
    parser.add_argument("--relationships", "-r", type=int, default=3,
                        help="Avg relationships per entity (default: 3)")
    parser.add_argument("--no-docker", action="store_true",
                        help="Don't use docker compose")

    args = parser.parse_args()

    generator = KnowledgeGraphGenerator(use_docker=not args.no_docker)
    result = generator.generate(
        num_entities=args.entities,
        relationships_per_entity=args.relationships
    )

    print_result(result)
    sys.exit(0 if result.errors == 0 else 1)


if __name__ == "__main__":
    main()
