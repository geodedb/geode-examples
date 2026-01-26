# Tutorial 3: Transactions

This tutorial covers Geode's transaction management including ACID guarantees,
savepoints, and isolation levels.

**CANARY: REQ=REQ-TUTORIAL-003; FEATURE="Transactions"; ASPECT=Documentation; STATUS=COMPLETE**

## Prerequisites

- Completed Tutorial 1: Getting Started
- Running Geode instance
- Basic understanding of ACID properties

## ACID Properties in Geode

Geode provides full ACID transaction support:

- **Atomicity**: All operations in a transaction succeed or all fail
- **Consistency**: Database remains in a valid state
- **Isolation**: Concurrent transactions don't interfere
- **Durability**: Committed transactions persist

## Basic Transactions

### Begin, Commit, and Rollback

```gql
-- Begin a transaction
BEGIN TRANSACTION;

-- Create data
CREATE (:Account {id: 'acc_001', balance: 1000});
CREATE (:Account {id: 'acc_002', balance: 500});

-- Commit changes
COMMIT;
```

### Transaction with Rollback

```gql
-- Begin transaction
BEGIN TRANSACTION;

-- Make changes
CREATE (:TempData {value: 'will be discarded'});

-- Oops, we don't want this
ROLLBACK;

-- Verify nothing was created
MATCH (t:TempData) RETURN count(t);  -- Returns 0
```

## Savepoints

Savepoints allow partial rollback within a transaction:

```gql
BEGIN TRANSACTION;

-- Create order
CREATE (:Order {id: 'order_1', status: 'pending'});

-- Create savepoint
SAVEPOINT after_order;

-- Add items
CREATE (:OrderItem {order_id: 'order_1', product: 'A', qty: 2});
CREATE (:OrderItem {order_id: 'order_1', product: 'B', qty: 1});

-- Create another savepoint
SAVEPOINT after_items;

-- Oops, add invalid item
CREATE (:OrderItem {order_id: 'order_1', product: 'INVALID', qty: 0});

-- Rollback to before the invalid item
ROLLBACK TO after_items;

-- Continue with valid operations
MATCH (o:Order {id: 'order_1'}) SET o.status = 'confirmed';

-- Commit final state
COMMIT;
```

## Atomic Money Transfer

The classic example of why we need transactions:

```gql
-- Setup accounts
CREATE (:Account {id: 'alice', balance: 1000});
CREATE (:Account {id: 'bob', balance: 200});

-- Atomic transfer
BEGIN TRANSACTION;

-- Debit source
MATCH (a:Account {id: 'alice'})
WHERE a.balance >= 300
SET a.balance = a.balance - 300;

-- Credit destination
MATCH (b:Account {id: 'bob'})
SET b.balance = b.balance + 300;

COMMIT;

-- Verify
MATCH (a:Account) RETURN a.id, a.balance ORDER BY a.id;
```

Output:
```
+-------+---------+
| a.id  | balance |
+-------+---------+
| alice | 700     |
| bob   | 500     |
+-------+---------+
```

## Isolation Levels

Geode supports 6 isolation levels:

| Level | Dirty Read | Non-Repeatable Read | Phantom Read |
|-------|------------|---------------------|--------------|
| READ UNCOMMITTED | Yes | Yes | Yes |
| READ COMMITTED | No | Yes | Yes |
| REPEATABLE READ | No | No | Yes |
| SNAPSHOT | No | No | No |
| SERIALIZABLE | No | No | No |
| LINEARIZABLE | No | No | No |

### Setting Isolation Level

```gql
-- Set isolation level for transaction
BEGIN TRANSACTION
ISOLATION LEVEL SERIALIZABLE;

-- Your operations here
MATCH (a:Account) RETURN a;

COMMIT;
```

### Read Committed (Default)

```gql
-- Session 1
BEGIN TRANSACTION;
MATCH (a:Account {id: 'alice'}) SET a.balance = 500;
-- Not committed yet

-- Session 2 (concurrent)
BEGIN TRANSACTION ISOLATION LEVEL READ COMMITTED;
-- Sees original value (1000), not uncommitted 500
MATCH (a:Account {id: 'alice'}) RETURN a.balance;
COMMIT;

-- Session 1
COMMIT;
```

### Serializable

```gql
-- Serializable prevents all anomalies
BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;

-- These operations are fully isolated
MATCH (a:Account) WHERE a.balance > 100 RETURN a;
CREATE (:AuditLog {action: 'balance_check', timestamp: datetime()});

COMMIT;
```

## Error Handling

Transactions automatically rollback on error:

```gql
BEGIN TRANSACTION;

-- Valid operation
CREATE (:ValidData {value: 1});

-- This will fail (duplicate key, constraint violation, etc.)
CREATE (:UniqueData {id: 'existing_id'});  -- Fails

-- Transaction is rolled back
-- ValidData was not persisted
```

## Best Practices

### Keep Transactions Short

```gql
-- BAD: Long-running transaction
BEGIN TRANSACTION;
-- Many operations
-- Holds locks for long time
COMMIT;

-- GOOD: Minimal transaction scope
-- Do read-only work outside transaction
MATCH (items:Item) WHERE items.status = 'pending'
WITH collect(items) AS pending_items

-- Short transaction for updates
BEGIN TRANSACTION;
UNWIND pending_items AS item
SET item.status = 'processed';
COMMIT;
```

### Use Savepoints for Complex Operations

```gql
BEGIN TRANSACTION;

-- Phase 1: Core changes
CREATE (:CoreData {id: 1});
SAVEPOINT core_complete;

-- Phase 2: Optional enrichment (might fail)
-- If this fails, we can still keep core changes
MATCH (c:CoreData {id: 1})
SET c.enriched = externalLookup(c.id);  -- Might fail

-- If enrichment failed
ROLLBACK TO core_complete;

COMMIT;
```

### Retry on Serialization Failure

```python
# Python pseudo-code for retry logic
max_retries = 3
for attempt in range(max_retries):
    try:
        async with client.transaction(isolation='SERIALIZABLE') as tx:
            await tx.execute("...")
            await tx.commit()
        break
    except SerializationError:
        if attempt == max_retries - 1:
            raise
        await asyncio.sleep(0.1 * (2 ** attempt))  # Exponential backoff
```

## Transaction in Client Libraries

### Python

```python
async with client.transaction() as tx:
    await tx.execute("CREATE (:Node {value: 1})")
    await tx.execute("CREATE (:Node {value: 2})")
    # Commits automatically on success
    # Rolls back on exception
```

### Go

```go
tx, err := db.BeginTx(ctx, &sql.TxOptions{
    Isolation: sql.LevelSerializable,
})
if err != nil {
    return err
}
defer tx.Rollback()

_, err = tx.ExecContext(ctx, "CREATE (:Node {value: 1})")
if err != nil {
    return err
}

return tx.Commit()
```

### Rust

```rust
let mut tx = client.begin_transaction().await?;
tx.execute("CREATE (:Node {value: 1})").await?;
tx.execute("CREATE (:Node {value: 2})").await?;
tx.commit().await?;
```

## Practice Exercises

### Exercise 1: Bank Transfer

Implement a safe money transfer:
1. Check source has sufficient funds
2. Debit source account
3. Credit destination account
4. Create audit log entry

### Exercise 2: Order Processing

Implement order processing with savepoints:
1. Create order record
2. Savepoint: after order
3. Reserve inventory
4. Savepoint: after reservation
5. Process payment (might fail)
6. On payment failure, rollback to after_reservation
7. Commit or rollback appropriately

## GQL Files

See the `examples/` directory:
- `01_basic_transaction.gql`
- `02_savepoints.gql`
- `03_money_transfer.gql`
- `04_isolation_levels.gql`

## Summary

You've learned:
- ACID properties in Geode
- BEGIN, COMMIT, ROLLBACK
- Savepoints for partial rollback
- 6 isolation levels
- Error handling
- Best practices

Next: [Tutorial 4: Vector Search](../04_vector_search/)
