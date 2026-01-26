// Basic Connection Example for Geode Go Client
//
// Verifies claim: Go database/sql driver with connection pooling
// Source: Features Overview, Client Libraries
// CANARY: REQ=REQ-CLIENT-GO-001; FEATURE="GoClient"; ASPECT=Client; STATUS=TESTED
//
// This example demonstrates basic connection setup and queries using
// the standard database/sql interface.
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
	// Connection string format: geode://host:port
	// Default port is 3141 (QUIC+TLS)
	connStr := "geode://localhost:3141"

	// Open connection using standard database/sql interface
	// The driver handles QUIC+TLS connection automatically
	db, err := sql.Open("geode", connStr)
	if err != nil {
		log.Fatalf("Failed to open database: %v", err)
	}
	defer db.Close()

	// Configure connection pool (production settings)
	db.SetMaxOpenConns(100)       // Maximum open connections
	db.SetMaxIdleConns(25)        // Maximum idle connections
	db.SetConnMaxLifetime(5 * time.Minute) // Connection lifetime
	db.SetConnMaxIdleTime(1 * time.Minute) // Idle timeout

	// Create context with timeout for operations
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// Verify connection
	fmt.Println("Connecting to Geode...")
	if err := db.PingContext(ctx); err != nil {
		log.Fatalf("Failed to ping database: %v", err)
	}
	fmt.Println("Connected successfully!")

	// Create sample data
	fmt.Println("\nCreating sample data...")
	_, err = db.ExecContext(ctx, `
		CREATE (:Person {name: 'Alice', age: 30, city: 'New York'})
	`)
	if err != nil {
		log.Printf("Warning: Could not create Alice: %v", err)
	}

	_, err = db.ExecContext(ctx, `
		CREATE (:Person {name: 'Bob', age: 25, city: 'San Francisco'})
	`)
	if err != nil {
		log.Printf("Warning: Could not create Bob: %v", err)
	}

	// Query data using standard interface
	fmt.Println("\nQuerying data...")
	rows, err := db.QueryContext(ctx, `
		MATCH (p:Person)
		RETURN p.name AS name, p.age AS age, p.city AS city
		ORDER BY p.name
	`)
	if err != nil {
		log.Fatalf("Failed to query: %v", err)
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
			log.Printf("Error scanning row: %v", err)
			continue
		}

		fmt.Printf("Name: %-10s Age: %-3d City: %s\n", name, age, city)
	}
	fmt.Println("----------------------------------------")

	if err := rows.Err(); err != nil {
		log.Printf("Error iterating results: %v", err)
	}

	// Query single value
	var count int
	err = db.QueryRowContext(ctx, "MATCH (p:Person) RETURN count(p)").Scan(&count)
	if err != nil {
		log.Printf("Error counting: %v", err)
	} else {
		fmt.Printf("\nTotal persons: %d\n", count)
	}

	// Cleanup
	fmt.Println("\nCleaning up...")
	_, err = db.ExecContext(ctx, "MATCH (p:Person) DETACH DELETE p")
	if err != nil {
		log.Printf("Warning: Cleanup failed: %v", err)
	}

	fmt.Println("\nGo client basic connection example completed successfully!")
}
