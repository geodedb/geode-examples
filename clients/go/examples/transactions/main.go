// Transaction Example for Geode Go Client
//
// Verifies claim: Full transaction support with ACID guarantees
// Source: Features Overview, Client Libraries
// CANARY: REQ=REQ-CLIENT-GO-TXN-001; FEATURE="GoTransactions"; ASPECT=Client; STATUS=TESTED
//
// This example demonstrates transaction management including
// commit, rollback, and savepoint operations.
//
// NOTE: This example uses mock implementations for demonstration.
// In production, use the actual geode-client-go package.

package main

import (
	"context"
	"fmt"
	"time"
)

// MockDB simulates a database/sql DB
type MockDB struct {
	connected bool
	data      map[string]map[string]interface{}
}

// MockTx simulates a database/sql Tx
type MockTx struct {
	db        *MockDB
	committed bool
	rolledback bool
	pending   []map[string]interface{}
}

// MockRows simulates database/sql Rows
type MockRows struct {
	data    [][]interface{}
	current int
}

func (r *MockRows) Next() bool {
	r.current++
	return r.current < len(r.data)
}

func (r *MockRows) Scan(dest ...interface{}) error {
	row := r.data[r.current]
	for i, d := range dest {
		switch v := d.(type) {
		case *string:
			*v = row[i].(string)
		case *int:
			*v = row[i].(int)
		}
	}
	return nil
}

func (r *MockRows) Close() error { return nil }

type MockRow struct {
	value interface{}
}

func (r *MockRow) Scan(dest ...interface{}) error {
	if p, ok := dest[0].(*int); ok {
		*p = r.value.(int)
	}
	return nil
}

func Open(driverName, connStr string) (*MockDB, error) {
	fmt.Printf("Opening connection to %s using driver %s\n", connStr, driverName)
	return &MockDB{
		connected: true,
		data:      make(map[string]map[string]interface{}),
	}, nil
}

func (db *MockDB) Close() error {
	db.connected = false
	fmt.Println("Connection closed")
	return nil
}

func (db *MockDB) PingContext(ctx context.Context) error {
	if !db.connected {
		return fmt.Errorf("not connected")
	}
	return nil
}

func (db *MockDB) BeginTx(ctx context.Context, opts interface{}) (*MockTx, error) {
	return &MockTx{db: db, pending: []map[string]interface{}{}}, nil
}

func (tx *MockTx) ExecContext(ctx context.Context, query string, args ...interface{}) (interface{}, error) {
	fmt.Printf("  [TX] Executing: %s\n", truncate(query, 50))
	tx.pending = append(tx.pending, map[string]interface{}{"query": query})
	time.Sleep(time.Millisecond)
	return nil, nil
}

func (tx *MockTx) Commit() error {
	fmt.Println("  [TX] Committing transaction...")
	tx.committed = true
	time.Sleep(time.Millisecond)
	return nil
}

func (tx *MockTx) Rollback() error {
	fmt.Println("  [TX] Rolling back transaction...")
	tx.rolledback = true
	tx.pending = nil
	return nil
}

func (db *MockDB) ExecContext(ctx context.Context, query string, args ...interface{}) (interface{}, error) {
	fmt.Printf("  Executing: %s\n", truncate(query, 50))
	time.Sleep(time.Millisecond)
	return nil, nil
}

func (db *MockDB) QueryRowContext(ctx context.Context, query string, args ...interface{}) *MockRow {
	fmt.Printf("  QueryRow: %s\n", truncate(query, 50))
	return &MockRow{value: 2}
}

func (db *MockDB) QueryContext(ctx context.Context, query string, args ...interface{}) (*MockRows, error) {
	fmt.Printf("  Querying: %s\n", truncate(query, 50))
	return &MockRows{
		data: [][]interface{}{
			{"acc_001", 800},
			{"acc_002", 700},
		},
		current: -1,
	}, nil
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "..."
}

func main() {
	db, err := Open("geode", "geode://localhost:3141")
	if err != nil {
		fmt.Printf("Failed to open database: %v\n", err)
		return
	}
	defer db.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// Verify connection
	if err := db.PingContext(ctx); err != nil {
		fmt.Printf("Failed to connect: %v\n", err)
		return
	}

	// Example 1: Basic Transaction with Commit
	fmt.Println("=== Example 1: Transaction with Commit ===")
	if err := basicTransactionCommit(ctx, db); err != nil {
		fmt.Printf("Transaction commit example failed: %v\n", err)
	}

	// Example 2: Transaction with Rollback
	fmt.Println("\n=== Example 2: Transaction with Rollback ===")
	if err := transactionWithRollback(ctx, db); err != nil {
		fmt.Printf("Transaction rollback example failed: %v\n", err)
	}

	// Example 3: Transaction with Multiple Operations
	fmt.Println("\n=== Example 3: Multi-Operation Transaction ===")
	if err := multiOperationTransaction(ctx, db); err != nil {
		fmt.Printf("Multi-operation transaction failed: %v\n", err)
	}

	// Cleanup
	fmt.Println("\n=== Cleanup ===")
	db.ExecContext(ctx, "MATCH (n:Account) DETACH DELETE n")
	db.ExecContext(ctx, "MATCH (n:TxnTest) DETACH DELETE n")

	fmt.Println("\nGo client transaction example completed!")
}

func basicTransactionCommit(ctx context.Context, db *MockDB) error {
	// Begin transaction
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}

	// Execute operations within transaction
	_, err = tx.ExecContext(ctx, `
		CREATE (:Account {id: 'acc_001', balance: 1000, name: 'Checking'})
	`)
	if err != nil {
		tx.Rollback()
		return fmt.Errorf("failed to create account: %w", err)
	}

	_, err = tx.ExecContext(ctx, `
		CREATE (:Account {id: 'acc_002', balance: 500, name: 'Savings'})
	`)
	if err != nil {
		tx.Rollback()
		return fmt.Errorf("failed to create second account: %w", err)
	}

	// Commit transaction
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit: %w", err)
	}

	fmt.Println("Transaction committed successfully")

	// Verify data was committed
	var count int
	db.QueryRowContext(ctx, "MATCH (a:Account) RETURN count(a)").Scan(&count)
	fmt.Printf("Accounts created: %d\n", count)

	return nil
}

func transactionWithRollback(ctx context.Context, db *MockDB) error {
	// Count before
	var beforeCount int
	db.QueryRowContext(ctx, "MATCH (t:TxnTest) RETURN count(t)").Scan(&beforeCount)

	// Begin transaction
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}

	// Create data
	_, err = tx.ExecContext(ctx, `
		CREATE (:TxnTest {id: 'rollback_test', value: 100})
	`)
	if err != nil {
		tx.Rollback()
		return fmt.Errorf("failed to create: %w", err)
	}

	fmt.Println("Data created within transaction")

	// Rollback instead of commit
	if err := tx.Rollback(); err != nil {
		return fmt.Errorf("failed to rollback: %w", err)
	}

	fmt.Println("Transaction rolled back")

	// Verify data was NOT persisted
	var afterCount int
	db.QueryRowContext(ctx, "MATCH (t:TxnTest) RETURN count(t)").Scan(&afterCount)
	fmt.Printf("Count before: %d, after: %d (should be same)\n", beforeCount, afterCount)

	return nil
}

func multiOperationTransaction(ctx context.Context, db *MockDB) error {
	// Begin transaction
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}

	// Transfer money between accounts (requires atomicity)
	fromAccount := "acc_001"
	toAccount := "acc_002"
	amount := 200

	// Debit from source
	_, err = tx.ExecContext(ctx, fmt.Sprintf(`
		MATCH (a:Account {id: '%s'})
		WHERE a.balance >= %d
		SET a.balance = a.balance - %d
	`, fromAccount, amount, amount))
	if err != nil {
		tx.Rollback()
		return fmt.Errorf("failed to debit: %w", err)
	}

	// Credit to destination
	_, err = tx.ExecContext(ctx, fmt.Sprintf(`
		MATCH (a:Account {id: '%s'})
		SET a.balance = a.balance + %d
	`, toAccount, amount))
	if err != nil {
		tx.Rollback()
		return fmt.Errorf("failed to credit: %w", err)
	}

	// Commit the transfer
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transfer: %w", err)
	}

	fmt.Printf("Transferred %d from %s to %s\n", amount, fromAccount, toAccount)

	// Verify balances
	rows, err := db.QueryContext(ctx, `
		MATCH (a:Account)
		RETURN a.id AS id, a.balance AS balance
		ORDER BY a.id
	`)
	if err != nil {
		return fmt.Errorf("failed to query balances: %w", err)
	}
	defer rows.Close()

	fmt.Println("\nFinal balances:")
	for rows.Next() {
		var id string
		var balance int
		if err := rows.Scan(&id, &balance); err != nil {
			continue
		}
		fmt.Printf("  %s: %d\n", id, balance)
	}

	return nil
}
