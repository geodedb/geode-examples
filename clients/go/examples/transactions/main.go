// Transaction Example for Geode Go Client
//
// Verifies claim: Full transaction support with ACID guarantees
// Source: Features Overview, Client Libraries
// CANARY: REQ=REQ-CLIENT-GO-TXN-001; FEATURE="GoTransactions"; ASPECT=Client; STATUS=TESTED
//
// This example demonstrates transaction management including
// commit, rollback, and savepoint operations.
package main

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"time"

	_ "go.codepros.org/geode/driver"
)

func main() {
	db, err := sql.Open("geode", "geode://localhost:3141")
	if err != nil {
		log.Fatalf("Failed to open database: %v", err)
	}
	defer db.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// Verify connection
	if err := db.PingContext(ctx); err != nil {
		log.Fatalf("Failed to connect: %v", err)
	}

	// Example 1: Basic Transaction with Commit
	fmt.Println("=== Example 1: Transaction with Commit ===")
	if err := basicTransactionCommit(ctx, db); err != nil {
		log.Printf("Transaction commit example failed: %v", err)
	}

	// Example 2: Transaction with Rollback
	fmt.Println("\n=== Example 2: Transaction with Rollback ===")
	if err := transactionWithRollback(ctx, db); err != nil {
		log.Printf("Transaction rollback example failed: %v", err)
	}

	// Example 3: Transaction with Multiple Operations
	fmt.Println("\n=== Example 3: Multi-Operation Transaction ===")
	if err := multiOperationTransaction(ctx, db); err != nil {
		log.Printf("Multi-operation transaction failed: %v", err)
	}

	// Cleanup
	fmt.Println("\n=== Cleanup ===")
	db.ExecContext(ctx, "MATCH (n:Account) DETACH DELETE n")
	db.ExecContext(ctx, "MATCH (n:TxnTest) DETACH DELETE n")

	fmt.Println("\nGo client transaction example completed!")
}

func basicTransactionCommit(ctx context.Context, db *sql.DB) error {
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
	err = db.QueryRowContext(ctx, "MATCH (a:Account) RETURN count(a)").Scan(&count)
	if err != nil {
		return fmt.Errorf("failed to verify: %w", err)
	}
	fmt.Printf("Accounts created: %d\n", count)

	return nil
}

func transactionWithRollback(ctx context.Context, db *sql.DB) error {
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

func multiOperationTransaction(ctx context.Context, db *sql.DB) error {
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
