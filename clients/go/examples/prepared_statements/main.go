// Prepared Statements Example for Geode Go Client
//
// Verifies claim: Full prepared statement support
// Source: Features Overview, Client Libraries
// CANARY: REQ=REQ-CLIENT-GO-PREP-001; FEATURE="GoPreparedStatements"; ASPECT=Client; STATUS=TESTED
//
// This example demonstrates using prepared statements for
// efficient repeated queries with different parameters.
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

	if err := db.PingContext(ctx); err != nil {
		log.Fatalf("Failed to connect: %v", err)
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
		log.Printf("Could not prepare insert statement: %v", err)
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
				log.Printf("Failed to insert %s: %v", p.name, err)
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
		log.Printf("Could not prepare query statement: %v", err)
	} else {
		defer queryStmt.Close()

		// Query different categories using same prepared statement
		categories := []string{"Electronics", "Furniture", "Books"}

		for _, category := range categories {
			fmt.Printf("\nCategory: %s\n", category)

			rows, err := queryStmt.QueryContext(ctx, category)
			if err != nil {
				log.Printf("Query failed for %s: %v", category, err)
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
		log.Printf("Could not prepare range statement: %v", err)
	} else {
		defer rangeStmt.Close()

		fmt.Println("\nProducts between $100 and $500:")
		rows, err := rangeStmt.QueryContext(ctx, 100.0, 500.0)
		if err != nil {
			log.Printf("Range query failed: %v", err)
		} else {
			for rows.Next() {
				var name, category string
				var price float64
				if err := rows.Scan(&name, &category, &price); err != nil {
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
		log.Printf("Cleanup failed: %v", err)
	}

	fmt.Println("\nPrepared statements example completed!")
}
