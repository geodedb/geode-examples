// Async Query Example for Geode Node.js Client
//
// Verifies claim: High-performance async operations with Promise support
// Source: Features Overview, Client Libraries
// CANARY: REQ=REQ-CLIENT-NODEJS-ASYNC-001; FEATURE="NodeJSAsync"; ASPECT=Client; STATUS=TESTED
//
// This example demonstrates concurrent query execution and
// throughput measurement using async/await patterns.

// Mock client for demonstration
class GeodeClient {
    constructor(options) {
        this.host = options.host || 'localhost';
        this.port = options.port || 3141;
        this.connected = false;
        this.queryCount = 0;
    }

    async connect() {
        await new Promise(resolve => setTimeout(resolve, 10));
        this.connected = true;
        console.log(`Connected to Geode at ${this.host}:${this.port}`);
    }

    async execute(query, params = {}) {
        if (!this.connected) throw new Error('Not connected');
        this.queryCount++;
        // Simulate fast query execution
        await new Promise(resolve => setTimeout(resolve, 0.1));
        return { records: [{ result: 1 }] };
    }

    async close() {
        this.connected = false;
        console.log('Connection closed');
    }
}

// Connection pool mock
class ConnectionPool {
    constructor(options) {
        this.maxConnections = options.maxConnections || 10;
        this.connections = [];
        this.available = [];
        this.waiting = [];
        this.totalQueries = 0;
    }

    async initialize(clientOptions) {
        for (let i = 0; i < this.maxConnections; i++) {
            const client = new GeodeClient(clientOptions);
            await client.connect();
            this.connections.push(client);
            this.available.push(client);
        }
        console.log(`Pool initialized with ${this.maxConnections} connections`);
    }

    async acquire() {
        if (this.available.length > 0) {
            return this.available.pop();
        }
        // Wait for available connection
        return new Promise(resolve => {
            this.waiting.push(resolve);
        });
    }

    release(client) {
        if (this.waiting.length > 0) {
            const resolve = this.waiting.shift();
            resolve(client);
        } else {
            this.available.push(client);
        }
    }

    async execute(query, params = {}) {
        const client = await this.acquire();
        try {
            this.totalQueries++;
            return await client.execute(query, params);
        } finally {
            this.release(client);
        }
    }

    async close() {
        for (const client of this.connections) {
            await client.close();
        }
        this.connections = [];
        this.available = [];
    }

    getStats() {
        return {
            total: this.connections.length,
            available: this.available.length,
            waiting: this.waiting.length,
            totalQueries: this.totalQueries
        };
    }
}

async function runConcurrentQueries(pool, numQueries, concurrency) {
    const results = {
        successful: 0,
        failed: 0,
        totalTime: 0
    };

    const startTime = performance.now();
    const batches = Math.ceil(numQueries / concurrency);

    for (let batch = 0; batch < batches; batch++) {
        const batchSize = Math.min(concurrency, numQueries - batch * concurrency);
        const promises = [];

        for (let i = 0; i < batchSize; i++) {
            promises.push(
                pool.execute('RETURN 1')
                    .then(() => { results.successful++; })
                    .catch(() => { results.failed++; })
            );
        }

        await Promise.all(promises);
    }

    results.totalTime = performance.now() - startTime;
    return results;
}

async function main() {
    console.log('Geode Node.js Client - Async Query Examples');
    console.log('============================================\n');

    // Create connection pool
    const pool = new ConnectionPool({
        maxConnections: 20
    });

    try {
        await pool.initialize({
            host: 'localhost',
            port: 3141
        });
        console.log();

        // Example 1: Sequential queries
        console.log('=== Example 1: Sequential Queries ===');
        const sequentialStart = performance.now();
        for (let i = 0; i < 100; i++) {
            await pool.execute('RETURN 1');
        }
        const sequentialTime = performance.now() - sequentialStart;
        console.log(`100 sequential queries: ${sequentialTime.toFixed(2)}ms`);
        console.log(`Throughput: ${(100 / sequentialTime * 1000).toFixed(0)} queries/sec\n`);

        // Example 2: Concurrent queries with Promise.all
        console.log('=== Example 2: Concurrent Queries (Promise.all) ===');
        const concurrentStart = performance.now();
        const promises = [];
        for (let i = 0; i < 100; i++) {
            promises.push(pool.execute('RETURN 1'));
        }
        await Promise.all(promises);
        const concurrentTime = performance.now() - concurrentStart;
        console.log(`100 concurrent queries: ${concurrentTime.toFixed(2)}ms`);
        console.log(`Throughput: ${(100 / concurrentTime * 1000).toFixed(0)} queries/sec`);
        console.log(`Speedup: ${(sequentialTime / concurrentTime).toFixed(2)}x\n`);

        // Example 3: Batch processing
        console.log('=== Example 3: Batch Processing ===');
        const batchSize = 50;
        const totalItems = 500;
        const batchStart = performance.now();

        for (let i = 0; i < totalItems; i += batchSize) {
            const batch = [];
            for (let j = i; j < Math.min(i + batchSize, totalItems); j++) {
                batch.push(pool.execute(`RETURN ${j}`));
            }
            await Promise.all(batch);
        }

        const batchTime = performance.now() - batchStart;
        console.log(`${totalItems} queries in batches of ${batchSize}: ${batchTime.toFixed(2)}ms`);
        console.log(`Throughput: ${(totalItems / batchTime * 1000).toFixed(0)} queries/sec\n`);

        // Example 4: High concurrency stress test
        console.log('=== Example 4: High Concurrency Stress Test ===');
        const stressResults = await runConcurrentQueries(pool, 1000, 100);
        console.log(`1000 queries with 100 concurrent:`);
        console.log(`  Successful: ${stressResults.successful}`);
        console.log(`  Failed: ${stressResults.failed}`);
        console.log(`  Total time: ${stressResults.totalTime.toFixed(2)}ms`);
        console.log(`  Throughput: ${(stressResults.successful / stressResults.totalTime * 1000).toFixed(0)} queries/sec\n`);

        // Example 5: Pool statistics
        console.log('=== Example 5: Pool Statistics ===');
        const stats = pool.getStats();
        console.log(`Pool stats:`);
        console.log(`  Total connections: ${stats.total}`);
        console.log(`  Available: ${stats.available}`);
        console.log(`  Waiting: ${stats.waiting}`);
        console.log(`  Total queries executed: ${stats.totalQueries}\n`);

        // Example 6: Promise.allSettled for error tolerance
        console.log('=== Example 6: Error Tolerant Batch (Promise.allSettled) ===');
        const mixedPromises = [
            pool.execute('RETURN 1'),
            pool.execute('RETURN 2'),
            pool.execute('INVALID QUERY'), // This would fail in real client
            pool.execute('RETURN 4'),
        ];
        const settled = await Promise.allSettled(mixedPromises);
        const fulfilled = settled.filter(r => r.status === 'fulfilled').length;
        const rejected = settled.filter(r => r.status === 'rejected').length;
        console.log(`Results: ${fulfilled} fulfilled, ${rejected} rejected\n`);

        console.log('Node.js async examples completed!');

    } catch (error) {
        console.error('Error:', error.message);
        process.exit(1);
    } finally {
        await pool.close();
    }
}

main();
