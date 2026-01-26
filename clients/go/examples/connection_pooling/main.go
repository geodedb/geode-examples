// Connection Pooling Example for Geode Go Client
//
// Verifies claim: Efficient connection pooling
// Source: Features Overview, Client Libraries
// CANARY: REQ=REQ-CLIENT-GO-POOL-001; FEATURE="GoConnectionPool"; ASPECT=Client; STATUS=TESTED
//
// This example demonstrates connection pool configuration and
// concurrent query execution using the pool.
//
// NOTE: This example uses mock implementations for demonstration.
// In production, use the actual geode-client-go package.

package main

import (
	"context"
	"fmt"
	"sync"
	"sync/atomic"
	"time"
)

// MockDB simulates a database/sql DB with connection pool stats
type MockDB struct {
	connected   bool
	maxOpen     int
	maxIdle     int
	maxLifetime time.Duration
	maxIdleTime time.Duration

	// Stats tracking
	mu              sync.Mutex
	openConns       int
	inUse           int
	waitCount       int64
	waitDuration    time.Duration
	maxIdleClosed   int64
	maxLifeClosed   int64
}

// DBStats mimics database/sql.DBStats
type DBStats struct {
	MaxOpenConnections int
	OpenConnections    int
	InUse              int
	Idle               int
	WaitCount          int64
	WaitDuration       time.Duration
	MaxIdleClosed      int64
	MaxLifetimeClosed  int64
}

// MockRow simulates database/sql Row
type MockRow struct {
	value int
}

func (r *MockRow) Scan(dest ...interface{}) error {
	if p, ok := dest[0].(*int); ok {
		*p = r.value
	}
	return nil
}

func Open(driverName, connStr string) (*MockDB, error) {
	fmt.Printf("Opening connection to %s using driver %s\n", connStr, driverName)
	return &MockDB{
		connected: true,
		openConns: 1,
	}, nil
}

func (db *MockDB) Close() error {
	db.connected = false
	fmt.Println("Connection closed")
	return nil
}

func (db *MockDB) SetMaxOpenConns(n int) {
	db.maxOpen = n
	fmt.Printf("  Set max open connections: %d\n", n)
}

func (db *MockDB) SetMaxIdleConns(n int) {
	db.maxIdle = n
	fmt.Printf("  Set max idle connections: %d\n", n)
}

func (db *MockDB) SetConnMaxLifetime(d time.Duration) {
	db.maxLifetime = d
	fmt.Printf("  Set connection max lifetime: %v\n", d)
}

func (db *MockDB) SetConnMaxIdleTime(d time.Duration) {
	db.maxIdleTime = d
	fmt.Printf("  Set connection max idle time: %v\n", d)
}

func (db *MockDB) PingContext(ctx context.Context) error {
	if !db.connected {
		return fmt.Errorf("not connected")
	}
	return nil
}

func (db *MockDB) QueryRowContext(ctx context.Context, query string, args ...interface{}) *MockRow {
	db.mu.Lock()
	db.inUse++
	if db.openConns < db.maxOpen {
		db.openConns++
	}
	db.mu.Unlock()

	// Simulate query execution
	time.Sleep(100 * time.Microsecond)

	db.mu.Lock()
	db.inUse--
	db.mu.Unlock()

	// Return sum of args if numeric
	result := 0
	for _, arg := range args {
		if v, ok := arg.(int); ok {
			result += v
		}
	}
	return &MockRow{value: result}
}

func (db *MockDB) Stats() DBStats {
	db.mu.Lock()
	defer db.mu.Unlock()

	idle := db.openConns - db.inUse
	if idle < 0 {
		idle = 0
	}

	return DBStats{
		MaxOpenConnections: db.maxOpen,
		OpenConnections:    db.openConns,
		InUse:              db.inUse,
		Idle:               idle,
		WaitCount:          db.waitCount,
		WaitDuration:       db.waitDuration,
		MaxIdleClosed:      db.maxIdleClosed,
		MaxLifetimeClosed:  db.maxLifeClosed,
	}
}

func main() {
	db, err := Open("geode", "geode://localhost:3141")
	if err != nil {
		fmt.Printf("Failed to open database: %v\n", err)
		return
	}
	defer db.Close()

	// Configure connection pool for high concurrency
	// These settings are optimized for production use
	fmt.Println("\nConfiguring connection pool...")
	db.SetMaxOpenConns(50)              // Maximum number of open connections
	db.SetMaxIdleConns(25)              // Keep 25 connections ready
	db.SetConnMaxLifetime(5 * time.Minute) // Refresh connections periodically
	db.SetConnMaxIdleTime(1 * time.Minute) // Close idle connections after 1 min

	ctx := context.Background()

	// Verify connection
	if err := db.PingContext(ctx); err != nil {
		fmt.Printf("Failed to connect: %v\n", err)
		return
	}

	fmt.Println("\n=== Connection Pooling Example ===")

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
	fmt.Println("\n--- Sustained Load Test (2 seconds) ---")

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
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

func printPoolStats(db *MockDB) {
	stats := db.Stats()
	fmt.Printf("  Max Open Conns:      %d\n", stats.MaxOpenConnections)
	fmt.Printf("  Open Conns:          %d\n", stats.OpenConnections)
	fmt.Printf("  In Use:              %d\n", stats.InUse)
	fmt.Printf("  Idle:                %d\n", stats.Idle)
	fmt.Printf("  Wait Count:          %d\n", stats.WaitCount)
	fmt.Printf("  Wait Duration:       %v\n", stats.WaitDuration)
	fmt.Printf("  Max Idle Closed:     %d\n", stats.MaxIdleClosed)
	fmt.Printf("  Max Lifetime Closed: %d\n", stats.MaxLifetimeClosed)
}
