// Connection Pooling Example for Geode Go Client
//
// Verifies claim: Efficient connection pooling
// Source: Features Overview, Client Libraries
// CANARY: REQ=REQ-CLIENT-GO-POOL-001; FEATURE="GoConnectionPool"; ASPECT=Client; STATUS=TESTED
//
// This example demonstrates connection pool configuration and
// concurrent query execution using the pool.
package main

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"sync"
	"sync/atomic"
	"time"

	_ "go.codepros.org/geode/driver"
)

func main() {
	db, err := sql.Open("geode", "geode://localhost:3141")
	if err != nil {
		log.Fatalf("Failed to open database: %v", err)
	}
	defer db.Close()

	// Configure connection pool for high concurrency
	// These settings are optimized for production use
	db.SetMaxOpenConns(50)        // Maximum number of open connections
	db.SetMaxIdleConns(25)        // Keep 25 connections ready
	db.SetConnMaxLifetime(5 * time.Minute) // Refresh connections periodically
	db.SetConnMaxIdleTime(1 * time.Minute) // Close idle connections after 1 min

	ctx := context.Background()

	// Verify connection
	if err := db.PingContext(ctx); err != nil {
		log.Fatalf("Failed to connect: %v", err)
	}

	fmt.Println("=== Connection Pooling Example ===\n")

	// Show initial pool stats
	fmt.Println("Initial Pool Stats:")
	printPoolStats(db)

	// Run concurrent queries
	fmt.Println("\n--- Running Concurrent Queries ---")

	var (
		wg           sync.WaitGroup
		successCount int64
		errorCount   int64
	)

	numWorkers := 20
	queriesPerWorker := 50

	start := time.Now()

	for i := 0; i < numWorkers; i++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()

			for j := 0; j < queriesPerWorker; j++ {
				ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)

				var result int
				err := db.QueryRowContext(ctx, "RETURN $1 + $2", workerID, j).Scan(&result)
				cancel()

				if err != nil {
					atomic.AddInt64(&errorCount, 1)
				} else {
					atomic.AddInt64(&successCount, 1)
				}
			}
		}(i)
	}

	// Wait for all workers
	wg.Wait()
	duration := time.Since(start)

	totalQueries := int64(numWorkers * queriesPerWorker)
	qps := float64(successCount) / duration.Seconds()

	fmt.Printf("\nResults:\n")
	fmt.Printf("  Workers:          %d\n", numWorkers)
	fmt.Printf("  Queries/worker:   %d\n", queriesPerWorker)
	fmt.Printf("  Total queries:    %d\n", totalQueries)
	fmt.Printf("  Successful:       %d\n", successCount)
	fmt.Printf("  Errors:           %d\n", errorCount)
	fmt.Printf("  Duration:         %v\n", duration)
	fmt.Printf("  Throughput:       %.0f queries/sec\n", qps)

	// Show pool stats after load
	fmt.Println("\n--- Pool Stats After Load ---")
	printPoolStats(db)

	// Demonstrate pool under sustained load
	fmt.Println("\n--- Sustained Load Test (10 seconds) ---")

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	successCount = 0
	errorCount = 0
	start = time.Now()

	// Create workers that run until context is done
	for i := 0; i < numWorkers; i++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()

			for {
				select {
				case <-ctx.Done():
					return
				default:
					queryCtx, queryCancel := context.WithTimeout(context.Background(), 2*time.Second)
					var result int
					err := db.QueryRowContext(queryCtx, "RETURN 1").Scan(&result)
					queryCancel()

					if err != nil {
						atomic.AddInt64(&errorCount, 1)
					} else {
						atomic.AddInt64(&successCount, 1)
					}
				}
			}
		}(i)
	}

	// Wait for timeout
	<-ctx.Done()
	wg.Wait()

	duration = time.Since(start)
	qps = float64(successCount) / duration.Seconds()

	fmt.Printf("\nSustained Load Results:\n")
	fmt.Printf("  Duration:         %v\n", duration)
	fmt.Printf("  Successful:       %d\n", successCount)
	fmt.Printf("  Errors:           %d\n", errorCount)
	fmt.Printf("  Throughput:       %.0f queries/sec\n", qps)

	// Final pool stats
	fmt.Println("\n--- Final Pool Stats ---")
	printPoolStats(db)

	fmt.Println("\nConnection pooling example completed!")
}

func printPoolStats(db *sql.DB) {
	stats := db.Stats()
	fmt.Printf("  Max Open Conns:   %d\n", stats.MaxOpenConnections)
	fmt.Printf("  Open Conns:       %d\n", stats.OpenConnections)
	fmt.Printf("  In Use:           %d\n", stats.InUse)
	fmt.Printf("  Idle:             %d\n", stats.Idle)
	fmt.Printf("  Wait Count:       %d\n", stats.WaitCount)
	fmt.Printf("  Wait Duration:    %v\n", stats.WaitDuration)
	fmt.Printf("  Max Idle Closed:  %d\n", stats.MaxIdleClosed)
	fmt.Printf("  Max Lifetime Closed: %d\n", stats.MaxLifetimeClosed)
}
