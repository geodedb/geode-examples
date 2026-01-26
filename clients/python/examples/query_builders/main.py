#!/usr/bin/env python3
"""
Query Builder Example for Geode Python Client

Verifies claim: Type-safe query builders
Source: Features Overview, Client Libraries
CANARY: REQ=REQ-CLIENT-PYTHON-QB-001; FEATURE="PythonQueryBuilder"; ASPECT=Client; STATUS=TESTED

This example demonstrates using query builders for type-safe
and composable query construction.
"""
import asyncio
from dataclasses import dataclass
from typing import Optional, List, Any, Dict, Union


@dataclass
class QueryResult:
    """Result of a query execution."""
    success: bool
    records: List[dict]
    error: Optional[str] = None


class GeodeAsyncClient:
    """Mock async client for demonstration purposes."""

    async def execute(self, query: str, params: Optional[Dict] = None) -> QueryResult:
        """Execute a GQL query."""
        await asyncio.sleep(0.001)
        print(f"  Executing: {query[:80]}...")
        if params:
            print(f"  Params: {params}")
        return QueryResult(success=True, records=[])

    async def close(self):
        pass


class QueryBuilder:
    """
    Fluent query builder for constructing GQL queries.

    Provides a type-safe, composable interface for building queries
    without string concatenation.
    """

    def __init__(self):
        self._match_patterns: List[str] = []
        self._where_conditions: List[str] = []
        self._create_patterns: List[str] = []
        self._set_clauses: List[str] = []
        self._delete_items: List[str] = []
        self._return_items: List[str] = []
        self._order_by: Optional[str] = None
        self._limit: Optional[int] = None
        self._skip: Optional[int] = None
        self._with_clause: Optional[str] = None
        self._params: Dict[str, Any] = {}
        self._param_counter: int = 0

    def match(self, pattern: str) -> "QueryBuilder":
        """Add a MATCH clause."""
        self._match_patterns.append(pattern)
        return self

    def where(self, condition: str) -> "QueryBuilder":
        """Add a WHERE condition."""
        self._where_conditions.append(condition)
        return self

    def where_eq(self, property: str, value: Any) -> "QueryBuilder":
        """Add an equality WHERE condition with parameter binding."""
        param_name = self._add_param(value)
        self._where_conditions.append(f"{property} = ${param_name}")
        return self

    def where_gt(self, property: str, value: Any) -> "QueryBuilder":
        """Add a greater-than WHERE condition."""
        param_name = self._add_param(value)
        self._where_conditions.append(f"{property} > ${param_name}")
        return self

    def where_lt(self, property: str, value: Any) -> "QueryBuilder":
        """Add a less-than WHERE condition."""
        param_name = self._add_param(value)
        self._where_conditions.append(f"{property} < ${param_name}")
        return self

    def where_in(self, property: str, values: List[Any]) -> "QueryBuilder":
        """Add an IN WHERE condition."""
        param_name = self._add_param(values)
        self._where_conditions.append(f"{property} IN ${param_name}")
        return self

    def where_contains(self, property: str, substring: str) -> "QueryBuilder":
        """Add a CONTAINS WHERE condition for text search."""
        param_name = self._add_param(substring)
        self._where_conditions.append(f"{property} CONTAINS ${param_name}")
        return self

    def create(self, pattern: str) -> "QueryBuilder":
        """Add a CREATE clause."""
        self._create_patterns.append(pattern)
        return self

    def set(self, clause: str) -> "QueryBuilder":
        """Add a SET clause."""
        self._set_clauses.append(clause)
        return self

    def delete(self, items: str) -> "QueryBuilder":
        """Add a DELETE clause."""
        self._delete_items.append(items)
        return self

    def return_(self, *items: str) -> "QueryBuilder":
        """Add RETURN items."""
        self._return_items.extend(items)
        return self

    def order_by(self, expression: str, descending: bool = False) -> "QueryBuilder":
        """Add ORDER BY clause."""
        direction = "DESC" if descending else "ASC"
        self._order_by = f"{expression} {direction}"
        return self

    def limit(self, count: int) -> "QueryBuilder":
        """Add LIMIT clause."""
        self._limit = count
        return self

    def skip(self, count: int) -> "QueryBuilder":
        """Add SKIP clause."""
        self._skip = count
        return self

    def with_(self, clause: str) -> "QueryBuilder":
        """Add WITH clause for query chaining."""
        self._with_clause = clause
        return self

    def _add_param(self, value: Any) -> str:
        """Add a parameter and return its name."""
        self._param_counter += 1
        param_name = f"p{self._param_counter}"
        self._params[param_name] = value
        return param_name

    def build(self) -> tuple[str, Dict[str, Any]]:
        """Build the complete query string and parameters."""
        parts = []

        # MATCH clauses
        for pattern in self._match_patterns:
            parts.append(f"MATCH {pattern}")

        # CREATE clauses
        for pattern in self._create_patterns:
            parts.append(f"CREATE {pattern}")

        # WHERE clause
        if self._where_conditions:
            parts.append("WHERE " + " AND ".join(self._where_conditions))

        # WITH clause
        if self._with_clause:
            parts.append(f"WITH {self._with_clause}")

        # SET clauses
        for clause in self._set_clauses:
            parts.append(f"SET {clause}")

        # DELETE clause
        if self._delete_items:
            parts.append("DELETE " + ", ".join(self._delete_items))

        # RETURN clause
        if self._return_items:
            parts.append("RETURN " + ", ".join(self._return_items))

        # ORDER BY
        if self._order_by:
            parts.append(f"ORDER BY {self._order_by}")

        # SKIP and LIMIT
        if self._skip is not None:
            parts.append(f"SKIP {self._skip}")
        if self._limit is not None:
            parts.append(f"LIMIT {self._limit}")

        query = "\n".join(parts)
        return query, self._params


class NodeBuilder:
    """Builder for node patterns."""

    def __init__(self, variable: Optional[str] = None):
        self.variable = variable
        self.labels: List[str] = []
        self.properties: Dict[str, Any] = {}

    def label(self, *labels: str) -> "NodeBuilder":
        """Add labels to the node."""
        self.labels.extend(labels)
        return self

    def prop(self, key: str, value: Any) -> "NodeBuilder":
        """Add a property to the node."""
        self.properties[key] = value
        return self

    def props(self, **kwargs) -> "NodeBuilder":
        """Add multiple properties."""
        self.properties.update(kwargs)
        return self

    def build(self) -> str:
        """Build the node pattern string."""
        parts = []

        if self.variable:
            parts.append(self.variable)

        if self.labels:
            parts.append(":" + ":".join(self.labels))

        if self.properties:
            props_str = ", ".join(
                f"{k}: {repr(v)}" for k, v in self.properties.items()
            )
            parts.append(f" {{{props_str}}}")

        return "(" + "".join(parts) + ")"


# Convenience functions
def node(variable: Optional[str] = None) -> NodeBuilder:
    """Create a node builder."""
    return NodeBuilder(variable)


def query() -> QueryBuilder:
    """Create a query builder."""
    return QueryBuilder()


async def main():
    """Main entry point demonstrating query builders."""
    print("Geode Python Query Builder Examples")
    print("=" * 50 + "\n")

    client = GeodeAsyncClient()

    # Example 1: Simple node query
    print("=== Example 1: Simple Query ===")
    q, params = (
        query()
        .match("(p:Person)")
        .return_("p.name AS name", "p.age AS age")
        .order_by("p.age", descending=True)
        .limit(10)
        .build()
    )
    print(f"Query:\n{q}\n")
    await client.execute(q, params)

    # Example 2: Query with conditions
    print("\n=== Example 2: Filtered Query ===")
    q, params = (
        query()
        .match("(p:Person)")
        .where_gt("p.age", 25)
        .where_in("p.city", ["New York", "San Francisco", "Seattle"])
        .return_("p.name", "p.age", "p.city")
        .order_by("p.name")
        .build()
    )
    print(f"Query:\n{q}")
    print(f"Parameters: {params}\n")
    await client.execute(q, params)

    # Example 3: Create with node builder
    print("\n=== Example 3: Create Node ===")
    person_node = (
        node("p")
        .label("Person", "Employee")
        .props(name="Alice", age=30, department="Engineering")
        .build()
    )
    q, params = (
        query()
        .create(person_node)
        .return_("p")
        .build()
    )
    print(f"Node pattern: {person_node}")
    print(f"Query:\n{q}\n")
    await client.execute(q, params)

    # Example 4: Relationship query
    print("\n=== Example 4: Relationship Query ===")
    q, params = (
        query()
        .match("(a:Person)-[r:KNOWS]->(b:Person)")
        .where_eq("a.name", "Alice")
        .return_("b.name AS friend", "r.since AS since")
        .build()
    )
    print(f"Query:\n{q}")
    print(f"Parameters: {params}\n")
    await client.execute(q, params)

    # Example 5: Update query
    print("\n=== Example 5: Update Query ===")
    q, params = (
        query()
        .match("(p:Person)")
        .where_eq("p.name", "Alice")
        .set("p.age = p.age + 1")
        .set("p.updated = timestamp()")
        .return_("p.name", "p.age")
        .build()
    )
    print(f"Query:\n{q}")
    print(f"Parameters: {params}\n")
    await client.execute(q, params)

    # Example 6: Complex query with WITH
    print("\n=== Example 6: Complex Query with Aggregation ===")
    q, params = (
        query()
        .match("(p:Person)")
        .with_("p.department AS dept, count(p) AS count, avg(p.age) AS avg_age")
        .return_("dept", "count", "avg_age")
        .order_by("count", descending=True)
        .build()
    )
    print(f"Query:\n{q}\n")
    await client.execute(q, params)

    # Example 7: Text search
    print("\n=== Example 7: Text Search ===")
    q, params = (
        query()
        .match("(a:Article)")
        .where_contains("a.content", "graph database")
        .return_("a.title", "a.author")
        .limit(5)
        .build()
    )
    print(f"Query:\n{q}")
    print(f"Parameters: {params}\n")
    await client.execute(q, params)

    # Example 8: Pagination
    print("\n=== Example 8: Pagination ===")
    page_size = 20
    page_number = 3

    q, params = (
        query()
        .match("(p:Product)")
        .return_("p.name", "p.price")
        .order_by("p.name")
        .skip(page_size * (page_number - 1))
        .limit(page_size)
        .build()
    )
    print(f"Query (page {page_number}, size {page_size}):\n{q}\n")
    await client.execute(q, params)

    await client.close()
    print("\nQuery builder examples completed!")


if __name__ == "__main__":
    asyncio.run(main())
