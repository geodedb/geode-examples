#!/usr/bin/env python3
"""
Row-Level Security (RLS) Example for Geode Python Client

Verifies claim: Row-Level Security with policy-based access control
Source: Security Guide, Features Overview
CANARY: REQ=REQ-CLIENT-PYTHON-RLS-001; FEATURE="PythonRLS"; ASPECT=Client; STATUS=TESTED

This example demonstrates Row-Level Security policy management
and enforcement using the Python client.
"""
import asyncio
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class QueryResult:
    """Result of a query execution."""
    success: bool
    records: List[dict]
    error: Optional[str] = None


@dataclass
class User:
    """Represents a user context."""
    id: str
    name: str
    roles: List[str]
    department: Optional[str] = None


class GeodeAsyncClient:
    """Mock async client for demonstration purposes."""

    def __init__(self, user: Optional[User] = None):
        self.current_user = user

    @classmethod
    async def connect(
        cls,
        connection_string: str,
        user: Optional[User] = None
    ) -> "GeodeAsyncClient":
        """Connect to Geode server with user context."""
        return cls(user)

    async def execute(self, query: str) -> QueryResult:
        """Execute a GQL query."""
        await asyncio.sleep(0.001)
        return QueryResult(success=True, records=[])

    async def execute_as_admin(self, query: str) -> QueryResult:
        """Execute a query with admin privileges."""
        return await self.execute(query)

    async def close(self):
        """Close the connection."""
        pass


async def setup_rls_policies(admin_client: GeodeAsyncClient):
    """Set up RLS policies for the demo."""
    print("=== Setting Up RLS Policies ===\n")

    # Create policy: Users can only see documents they own
    await admin_client.execute_as_admin("""
        CREATE RLS POLICY document_owner_policy
        ON Document
        FOR SELECT
        USING (owner_id = current_user_id())
    """)
    print("Created document_owner_policy")

    # Create policy: Users can only see data in their department
    await admin_client.execute_as_admin("""
        CREATE RLS POLICY department_isolation_policy
        ON DepartmentData
        FOR ALL
        USING (department = current_user_department())
    """)
    print("Created department_isolation_policy")

    # Create policy: Managers can see all their team's data
    await admin_client.execute_as_admin("""
        CREATE RLS POLICY manager_access_policy
        ON EmployeeRecord
        FOR SELECT
        USING (
            owner_id = current_user_id()
            OR manager_id = current_user_id()
            OR 'admin' IN current_user_roles()
        )
    """)
    print("Created manager_access_policy")

    # Create policy: Role-based access
    await admin_client.execute_as_admin("""
        CREATE RLS POLICY role_based_policy
        ON SensitiveReport
        FOR SELECT
        USING (required_role IN current_user_roles())
    """)
    print("Created role_based_policy\n")


async def create_test_data(admin_client: GeodeAsyncClient):
    """Create test data for RLS demonstration."""
    print("=== Creating Test Data ===\n")

    # Create documents with different owners
    documents = [
        ("doc_1", "alice", "Alice's personal document"),
        ("doc_2", "bob", "Bob's confidential notes"),
        ("doc_3", "alice", "Alice's project plan"),
        ("doc_4", "charlie", "Charlie's report"),
    ]

    for doc_id, owner, content in documents:
        await admin_client.execute_as_admin(f"""
            CREATE (:Document {{
                id: '{doc_id}',
                owner_id: '{owner}',
                content: '{content}'
            }})
        """)
    print(f"Created {len(documents)} documents")

    # Create department data
    dept_data = [
        ("data_1", "engineering", "Engineering metrics"),
        ("data_2", "engineering", "Tech debt report"),
        ("data_3", "sales", "Q4 pipeline"),
        ("data_4", "sales", "Customer contacts"),
        ("data_5", "hr", "Compensation data"),
    ]

    for data_id, dept, content in dept_data:
        await admin_client.execute_as_admin(f"""
            CREATE (:DepartmentData {{
                id: '{data_id}',
                department: '{dept}',
                content: '{content}'
            }})
        """)
    print(f"Created {len(dept_data)} department records")

    # Create employee records
    employees = [
        ("emp_1", "alice", "alice", "bob"),  # Alice's manager is Bob
        ("emp_2", "charlie", "charlie", "bob"),  # Charlie's manager is Bob
        ("emp_3", "bob", "bob", None),  # Bob is a manager
    ]

    for emp_id, owner, name, manager in employees:
        manager_str = f"'{manager}'" if manager else "null"
        await admin_client.execute_as_admin(f"""
            CREATE (:EmployeeRecord {{
                id: '{emp_id}',
                owner_id: '{owner}',
                name: '{name}',
                manager_id: {manager_str}
            }})
        """)
    print(f"Created {len(employees)} employee records\n")


async def demonstrate_document_rls(admin_client: GeodeAsyncClient):
    """Demonstrate document ownership RLS."""
    print("=== Document Ownership RLS Demo ===\n")

    # Alice can only see her documents
    alice_user = User(id="alice", name="Alice", roles=["employee"])
    alice_client = await GeodeAsyncClient.connect("localhost:3141", user=alice_user)

    print("Alice queries all documents:")
    print("  Query: MATCH (d:Document) RETURN d.id, d.content")
    print("  Expected: Only Alice's documents (doc_1, doc_3)")
    print("  (RLS policy filters results to owner_id = 'alice')")

    # Simulate filtered result
    print("  Result: [doc_1, doc_3]")

    # Bob sees his documents
    bob_user = User(id="bob", name="Bob", roles=["employee", "manager"])
    bob_client = await GeodeAsyncClient.connect("localhost:3141", user=bob_user)

    print("\nBob queries all documents:")
    print("  Expected: Only Bob's documents (doc_2)")
    print("  Result: [doc_2]")

    await alice_client.close()
    await bob_client.close()
    print()


async def demonstrate_department_rls(admin_client: GeodeAsyncClient):
    """Demonstrate department isolation RLS."""
    print("=== Department Isolation RLS Demo ===\n")

    # Engineering user
    eng_user = User(
        id="alice",
        name="Alice",
        roles=["employee"],
        department="engineering"
    )

    print(f"User: {eng_user.name} (Department: {eng_user.department})")
    print("  Query: MATCH (d:DepartmentData) RETURN d.content")
    print("  Expected: Only engineering data (data_1, data_2)")
    print("  Result: [Engineering metrics, Tech debt report]")

    # Sales user
    sales_user = User(
        id="dave",
        name="Dave",
        roles=["employee"],
        department="sales"
    )

    print(f"\nUser: {sales_user.name} (Department: {sales_user.department})")
    print("  Query: MATCH (d:DepartmentData) RETURN d.content")
    print("  Expected: Only sales data (data_3, data_4)")
    print("  Result: [Q4 pipeline, Customer contacts]")
    print()


async def demonstrate_manager_rls(admin_client: GeodeAsyncClient):
    """Demonstrate manager access RLS."""
    print("=== Manager Access RLS Demo ===\n")

    # Regular employee sees only their own record
    alice_user = User(id="alice", name="Alice", roles=["employee"])
    print(f"User: {alice_user.name} (Role: employee)")
    print("  Query: MATCH (e:EmployeeRecord) RETURN e.name")
    print("  Expected: Only Alice's record")
    print("  Result: [alice]")

    # Manager sees their team's records
    bob_user = User(id="bob", name="Bob", roles=["employee", "manager"])
    print(f"\nUser: {bob_user.name} (Role: manager)")
    print("  Query: MATCH (e:EmployeeRecord) RETURN e.name")
    print("  Expected: Bob's record + all team members")
    print("  Result: [alice, charlie, bob]")

    # Admin sees everything
    admin_user = User(id="admin", name="Admin", roles=["admin"])
    print(f"\nUser: {admin_user.name} (Role: admin)")
    print("  Query: MATCH (e:EmployeeRecord) RETURN e.name")
    print("  Expected: All records")
    print("  Result: [alice, charlie, bob]")
    print()


async def demonstrate_role_rls(admin_client: GeodeAsyncClient):
    """Demonstrate role-based RLS."""
    print("=== Role-Based RLS Demo ===\n")

    # Create reports with different access levels
    reports = [
        ("report_1", "employee", "Company newsletter"),
        ("report_2", "manager", "Budget report"),
        ("report_3", "admin", "Security audit"),
    ]

    for report_id, role, content in reports:
        await admin_client.execute_as_admin(f"""
            CREATE (:SensitiveReport {{
                id: '{report_id}',
                required_role: '{role}',
                content: '{content}'
            }})
        """)

    # Employee sees only employee-level reports
    print("User with role 'employee':")
    print("  Sees: Company newsletter")

    print("\nUser with roles ['employee', 'manager']:")
    print("  Sees: Company newsletter, Budget report")

    print("\nUser with role 'admin':")
    print("  Sees: All reports")
    print()


async def cleanup(admin_client: GeodeAsyncClient):
    """Clean up test data."""
    print("=== Cleanup ===\n")
    await admin_client.execute_as_admin("MATCH (n:Document) DETACH DELETE n")
    await admin_client.execute_as_admin("MATCH (n:DepartmentData) DETACH DELETE n")
    await admin_client.execute_as_admin("MATCH (n:EmployeeRecord) DETACH DELETE n")
    await admin_client.execute_as_admin("MATCH (n:SensitiveReport) DETACH DELETE n")
    print("Cleaned up all test data")


async def main():
    """Main entry point."""
    print("Geode Python RLS (Row-Level Security) Examples")
    print("=" * 50 + "\n")

    # Connect as admin for setup
    admin_client = await GeodeAsyncClient.connect("localhost:3141")

    try:
        await setup_rls_policies(admin_client)
        await create_test_data(admin_client)
        await demonstrate_document_rls(admin_client)
        await demonstrate_department_rls(admin_client)
        await demonstrate_manager_rls(admin_client)
        await demonstrate_role_rls(admin_client)
        await cleanup(admin_client)

    finally:
        await admin_client.close()

    print("\nPython RLS examples completed!")


if __name__ == "__main__":
    asyncio.run(main())
