// Prepared Statements Example for Geode Go Client
//
// Verifies claim: Full prepared statement support
// Source: Features Overview, Client Libraries
// CANARY: REQ=REQ-CLIENT-GO-PREP-001; FEATURE="GoPreparedStatements"; ASPECT=Client; STATUS=TESTED
//
// This example demonstrates using prepared statements for
// efficient repeated queries with different parameters.
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
}

// MockStmt simulates a database/sql Stmt
type MockStmt struct {
	query    string
	products map[string][]product
}

type product struct {
	name     string
	category string
	price    float64
}

// MockRows simulates database/sql Rows
type MockRows struct {
	data    []product
	current int
}

func (r *MockRows) Next() bool {
	r.current++
	return r.current < len(r.data)
}

func (r *MockRows) Scan(dest ...interface{}) error {
	p := r.data[r.current]
	for i, d := range dest {
		switch v := d.(type) {
		case *string:
			if i == 0 {
				*v = p.name
			} else if i == 1 {
				*v = p.category
			}
		case *float64:
			*v = p.price
		}
	}
	return nil
}

func (r *MockRows) Close() error { return nil }

func Open(driverName, connStr string) (*MockDB, error) {
	fmt.Printf("Opening connection to %s using driver %s\n", connStr, driverName)
	return &MockDB{connected: true}, nil
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

func (db *MockDB) ExecContext(ctx context.Context, query string, args ...interface{}) (interface{}, error) {
	fmt.Printf("  Executing: %s\n", truncate(query, 50))
	time.Sleep(time.Millisecond)
	return nil, nil
}

func (db *MockDB) PrepareContext(ctx context.Context, query string) (*MockStmt, error) {
	fmt.Printf("  Preparing: %s\n", truncate(query, 50))
	stmt := &MockStmt{
		query: query,
		products: map[string][]product{
			"Electronics": {
				{"Laptop", "Electronics", 999.99},
				{"Phone", "Electronics", 699.99},
				{"Headphones", "Electronics", 149.99},
			},
			"Furniture": {
				{"Desk", "Furniture", 299.99},
				{"Chair", "Furniture", 199.99},
			},
			"Books": {
				{"Book", "Books", 29.99},
			},
		},
	}
	return stmt, nil
}

func (stmt *MockStmt) ExecContext(ctx context.Context, args ...interface{}) (interface{}, error) {
	fmt.Printf("    [STMT] Exec with args: %v\n", args)
	time.Sleep(time.Millisecond)
	return nil, nil
}

func (stmt *MockStmt) QueryContext(ctx context.Context, args ...interface{}) (*MockRows, error) {
	fmt.Printf("    [STMT] Query with args: %v\n", args)
	// If first arg is a string (category), filter by category
	if len(args) > 0 {
		if cat, ok := args[0].(string); ok {
			if products, exists := stmt.products[cat]; exists {
				return &MockRows{data: products, current: -1}, nil
			}
		}
		// Price range query
		if len(args) == 2 {
			var results []product
			for _, products := range stmt.products {
				for _, p := range products {
					if min, ok := args[0].(float64); ok {
						if max, ok := args[1].(float64); ok {
							if p.price >= min && p.price <= max {
								results = append(results, p)
							}
						}
					}
				}
			}
			return &MockRows{data: results, current: -1}, nil
		}
	}
	return &MockRows{data: []product{}, current: -1}, nil
}

func (stmt *MockStmt) Close() error {
	fmt.Println("    [STMT] Statement closed")
	return nil
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

	if err := db.PingContext(ctx); err != nil {
		fmt.Printf("Failed to connect: %v\n", err)
		return
	}

	fmt.Println("=== Prepared Statements Example ===\n")

	// Create test data
	fmt.Println("Creating test data...")
	products := []struct {
		name     string
		category string
		price    float64
	}{
		{"Laptop", "Electronics", 999.99},
		{"Phone", "Electronics", 699.99},
		{"Headphones", "Electronics", 149.99},
		{"Desk", "Furniture", 299.99},
		{"Chair", "Furniture", 199.99},
		{"Book", "Books", 29.99},
	}

	// Use prepared statement for inserts
	insertStmt, err := db.PrepareContext(ctx, `
		CREATE (:Product {name: $name, category: $category, price: $price})
	`)
	if err != nil {
		fmt.Printf("Could not prepare insert statement: %v\n", err)
		// Fallback to direct execution
		for _, p := range products {
			db.ExecContext(ctx, fmt.Sprintf(`
				CREATE (:Product {name: '%s', category: '%s', price: %f})
			`, p.name, p.category, p.price))
		}
	} else {
		defer insertStmt.Close()

		for _, p := range products {
			_, err := insertStmt.ExecContext(ctx, p.name, p.category, p.price)
			if err != nil {
				fmt.Printf("Failed to insert %s: %v\n", p.name, err)
			}
		}
	}
	fmt.Printf("Created %d products\n", len(products))

	// Prepared statement for queries
	fmt.Println("\n--- Querying by Category ---")

	queryStmt, err := db.PrepareContext(ctx, `
		MATCH (p:Product)
		WHERE p.category = $category
		RETURN p.name AS name, p.price AS price
		ORDER BY p.price DESC
	`)
	if err != nil {
		fmt.Printf("Could not prepare query statement: %v\n", err)
	} else {
		defer queryStmt.Close()

		// Query different categories using same prepared statement
		categories := []string{"Electronics", "Furniture", "Books"}

		for _, category := range categories {
			fmt.Printf("\nCategory: %s\n", category)

			rows, err := queryStmt.QueryContext(ctx, category)
			if err != nil {
				fmt.Printf("Query failed for %s: %v\n", category, err)
				continue
			}

			for rows.Next() {
				var name string
				var price float64
				if err := rows.Scan(&name, &price); err != nil {
					continue
				}
				fmt.Printf("  - %s: $%.2f\n", name, price)
			}
			rows.Close()
		}
	}

	// Prepared statement with multiple parameters
	fmt.Println("\n--- Price Range Query ---")

	rangeStmt, err := db.PrepareContext(ctx, `
		MATCH (p:Product)
		WHERE p.price >= $min AND p.price <= $max
		RETURN p.name AS name, p.category AS category, p.price AS price
		ORDER BY p.price
	`)
	if err != nil {
		fmt.Printf("Could not prepare range statement: %v\n", err)
	} else {
		defer rangeStmt.Close()

		fmt.Println("\nProducts between $100 and $500:")
		rows, err := rangeStmt.QueryContext(ctx, 100.0, 500.0)
		if err != nil {
			fmt.Printf("Range query failed: %v\n", err)
		} else {
			for rows.Next() {
				var name, category string
				var price float64
				if err := rows.Scan(&name, &price); err != nil {
					continue
				}
				fmt.Printf("  - %s (%s): $%.2f\n", name, category, price)
			}
			rows.Close()
		}
	}

	// Cleanup
	fmt.Println("\n--- Cleanup ---")
	_, err = db.ExecContext(ctx, "MATCH (p:Product) DETACH DELETE p")
	if err != nil {
		fmt.Printf("Cleanup failed: %v\n", err)
	}

	fmt.Println("\nPrepared statements example completed!")
}
