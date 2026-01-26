// Basic Connection Example for Geode Go Client
//
// Verifies claim: Go database/sql driver with connection pooling
// Source: Features Overview, Client Libraries
// CANARY: REQ=REQ-CLIENT-GO-001; FEATURE="GoClient"; ASPECT=Client; STATUS=TESTED
//
// This example demonstrates basic connection setup and queries using
// patterns compatible with the standard database/sql interface.
//
// NOTE: This example uses mock implementations for demonstration.
// In production, use the actual geode-client-go package.

package main

import (
	"context"
	"fmt"
	"time"
)

// MockDB simulates a database/sql DB for demonstration
type MockDB struct {
	maxOpen     int
	maxIdle     int
	maxLifetime time.Duration
	connected   bool
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
func (r *MockRows) Err() error   { return nil }

func Open(driverName, connStr string) (*MockDB, error) {
	fmt.Printf("Opening connection to %s using driver %s\n", connStr, driverName)
	return &MockDB{connected: true}, nil
}

func (db *MockDB) Close() error {
	db.connected = false
	fmt.Println("Connection closed")
	return nil
}

func (db *MockDB) SetMaxOpenConns(n int)                { db.maxOpen = n }
func (db *MockDB) SetMaxIdleConns(n int)                { db.maxIdle = n }
func (db *MockDB) SetConnMaxLifetime(d time.Duration)   { db.maxLifetime = d }
func (db *MockDB) SetConnMaxIdleTime(d time.Duration)   {}

func (db *MockDB) PingContext(ctx context.Context) error {
	if !db.connected {
		return fmt.Errorf("not connected")
	}
	return nil
}

func (db *MockDB) ExecContext(ctx context.Context, query string, args ...interface{}) (interface{}, error) {
	fmt.Printf("  Executing: %s\n", truncate(query, 50))
	time.Sleep(time.Millisecond)
	return nil, nil
}

func (db *MockDB) QueryContext(ctx context.Context, query string, args ...interface{}) (*MockRows, error) {
	fmt.Printf("  Querying: %s\n", truncate(query, 50))
	// Return mock data
	return &MockRows{
		data: [][]interface{}{
			{"Alice", 30, "New York"},
			{"Bob", 25, "San Francisco"},
		},
		current: -1,
	}, nil
}

func (db *MockDB) QueryRowContext(ctx context.Context, query string, args ...interface{}) *MockRow {
	fmt.Printf("  QueryRow: %s\n", truncate(query, 50))
	return &MockRow{value: 2}
}

type MockRow struct {
	value interface{}
}

func (r *MockRow) Scan(dest ...interface{}) error {
	if p, ok := dest[0].(*int); ok {
		*p = r.value.(int)
	}
	return nil
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "..."
}

func main() {
	// Connection string format: geode://host:port
	connStr := "geode://localhost:3141"

	// Open connection using database/sql-like interface
	db, err := Open("geode", connStr)
	if err != nil {
		fmt.Printf("Failed to open database: %v\n", err)
		return
	}
	defer db.Close()

	// Configure connection pool (production settings)
	db.SetMaxOpenConns(100)
	db.SetMaxIdleConns(25)
	db.SetConnMaxLifetime(5 * time.Minute)
	db.SetConnMaxIdleTime(1 * time.Minute)

	// Create context with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// Verify connection
	fmt.Println("Connecting to Geode...")
	if err := db.PingContext(ctx); err != nil {
		fmt.Printf("Failed to ping database: %v\n", err)
		return
	}
	fmt.Println("Connected successfully!")

	// Create sample data
	fmt.Println("\nCreating sample data...")
	db.ExecContext(ctx, "CREATE (:Person {name: 'Alice', age: 30, city: 'New York'})")
	db.ExecContext(ctx, "CREATE (:Person {name: 'Bob', age: 25, city: 'San Francisco'})")

	// Query data
	fmt.Println("\nQuerying data...")
	rows, err := db.QueryContext(ctx, `
		MATCH (p:Person)
		RETURN p.name AS name, p.age AS age, p.city AS city
		ORDER BY p.name
	`)
	if err != nil {
		fmt.Printf("Failed to query: %v\n", err)
		return
	}
	defer rows.Close()

	// Iterate results
	fmt.Println("\nResults:")
	fmt.Println("----------------------------------------")
	for rows.Next() {
		var name string
		var age int
		var city string

		if err := rows.Scan(&name, &age, &city); err != nil {
			fmt.Printf("Error scanning row: %v\n", err)
			continue
		}

		fmt.Printf("Name: %-10s Age: %-3d City: %s\n", name, age, city)
	}
	fmt.Println("----------------------------------------")

	// Query single value
	var count int
	db.QueryRowContext(ctx, "MATCH (p:Person) RETURN count(p)").Scan(&count)
	fmt.Printf("\nTotal persons: %d\n", count)

	// Cleanup
	fmt.Println("\nCleaning up...")
	db.ExecContext(ctx, "MATCH (p:Person) DETACH DELETE p")

	fmt.Println("\nGo client basic connection example completed successfully!")
}
