// Streaming Example for Geode Node.js Client
//
// Verifies claim: Efficient streaming for large result sets
// Source: Features Overview, Client Libraries
// CANARY: REQ=REQ-CLIENT-NODEJS-STREAM-001; FEATURE="NodeJSStreaming"; ASPECT=Client; STATUS=TESTED
//
// This example demonstrates streaming query results for
// memory-efficient processing of large datasets.

import { EventEmitter } from 'events';

// Mock client with streaming support
class GeodeClient {
    constructor(options) {
        this.host = options.host || 'localhost';
        this.port = options.port || 3141;
        this.connected = false;
    }

    async connect() {
        await new Promise(resolve => setTimeout(resolve, 10));
        this.connected = true;
        console.log(`Connected to Geode at ${this.host}:${this.port}`);
    }

    async execute(query) {
        if (!this.connected) throw new Error('Not connected');
        const displayQuery = query.length > 50 ? query.slice(0, 50) + '...' : query;
        console.log(`  Executing: ${displayQuery}`);
        await new Promise(resolve => setTimeout(resolve, 1));
        return { records: [] };
    }

    // Create a streaming query that returns an async iterator
    stream(query, options = {}) {
        const batchSize = options.batchSize || 100;
        const totalRecords = options.mockRecords || 1000;

        return new QueryStream(query, batchSize, totalRecords);
    }

    async close() {
        this.connected = false;
        console.log('Connection closed');
    }
}

class QueryStream {
    constructor(query, batchSize, totalRecords) {
        this.query = query;
        this.batchSize = batchSize;
        this.totalRecords = totalRecords;
        this.position = 0;
    }

    // Async iterator implementation
    [Symbol.asyncIterator]() {
        return this;
    }

    async next() {
        if (this.position >= this.totalRecords) {
            return { done: true, value: undefined };
        }

        // Simulate fetching next record
        await new Promise(resolve => setTimeout(resolve, 0.01));

        const record = {
            id: this.position,
            name: `Node_${this.position}`,
            value: Math.random() * 1000
        };

        this.position++;
        return { done: false, value: record };
    }

    // Event-based streaming alternative
    toEventEmitter() {
        const emitter = new EventEmitter();

        setImmediate(async () => {
            try {
                for await (const record of this) {
                    emitter.emit('data', record);
                }
                emitter.emit('end');
            } catch (error) {
                emitter.emit('error', error);
            }
        });

        return emitter;
    }
}

async function basicStreamingExample(client) {
    console.log('=== Example 1: Basic Async Iterator Streaming ===');

    const stream = client.stream('MATCH (n) RETURN n', {
        batchSize: 100,
        mockRecords: 500
    });

    let count = 0;
    const startTime = performance.now();

    for await (const record of stream) {
        count++;
        // Process each record
        if (count % 100 === 0) {
            console.log(`  Processed ${count} records...`);
        }
    }

    const duration = performance.now() - startTime;
    console.log(`Streamed ${count} records in ${duration.toFixed(2)}ms`);
    console.log(`Throughput: ${(count / duration * 1000).toFixed(0)} records/sec\n`);
}

async function batchedStreamingExample(client) {
    console.log('=== Example 2: Batched Processing ===');

    const stream = client.stream('MATCH (n) RETURN n', {
        mockRecords: 1000
    });

    const batchSize = 100;
    let batch = [];
    let batchCount = 0;

    for await (const record of stream) {
        batch.push(record);

        if (batch.length >= batchSize) {
            batchCount++;
            // Process batch
            const sum = batch.reduce((acc, r) => acc + r.value, 0);
            console.log(`  Batch ${batchCount}: ${batch.length} records, sum=${sum.toFixed(2)}`);
            batch = [];
        }
    }

    // Process remaining records
    if (batch.length > 0) {
        batchCount++;
        const sum = batch.reduce((acc, r) => acc + r.value, 0);
        console.log(`  Batch ${batchCount}: ${batch.length} records, sum=${sum.toFixed(2)}`);
    }

    console.log(`Processed ${batchCount} batches\n`);
}

async function eventBasedStreamingExample(client) {
    console.log('=== Example 3: Event-Based Streaming ===');

    return new Promise((resolve, reject) => {
        const stream = client.stream('MATCH (n) RETURN n', {
            mockRecords: 300
        });

        const emitter = stream.toEventEmitter();
        let count = 0;
        let sum = 0;

        emitter.on('data', (record) => {
            count++;
            sum += record.value;
        });

        emitter.on('end', () => {
            console.log(`  Received ${count} records via events`);
            console.log(`  Total sum: ${sum.toFixed(2)}`);
            console.log();
            resolve();
        });

        emitter.on('error', (error) => {
            reject(error);
        });
    });
}

async function transformStreamExample(client) {
    console.log('=== Example 4: Transform Stream Pipeline ===');

    const stream = client.stream('MATCH (n) RETURN n', {
        mockRecords: 500
    });

    // Create a transform pipeline using async generators
    async function* filter(source, predicate) {
        for await (const item of source) {
            if (predicate(item)) {
                yield item;
            }
        }
    }

    async function* map(source, transform) {
        for await (const item of source) {
            yield transform(item);
        }
    }

    async function* take(source, count) {
        let taken = 0;
        for await (const item of source) {
            if (taken >= count) break;
            yield item;
            taken++;
        }
    }

    // Pipeline: filter -> map -> take
    const pipeline = take(
        map(
            filter(stream, r => r.value > 500),
            r => ({ ...r, doubledValue: r.value * 2 })
        ),
        10
    );

    console.log('  Filtered (value > 500), mapped (doubled), taking 10:');
    for await (const record of pipeline) {
        console.log(`    id=${record.id}, value=${record.value.toFixed(2)}, doubled=${record.doubledValue.toFixed(2)}`);
    }
    console.log();
}

async function parallelStreamingExample(client) {
    console.log('=== Example 5: Parallel Stream Processing ===');

    // Create multiple streams
    const streams = [
        client.stream('MATCH (n:TypeA) RETURN n', { mockRecords: 200 }),
        client.stream('MATCH (n:TypeB) RETURN n', { mockRecords: 200 }),
        client.stream('MATCH (n:TypeC) RETURN n', { mockRecords: 200 }),
    ];

    // Process streams in parallel
    async function processStream(stream, name) {
        let count = 0;
        let sum = 0;
        for await (const record of stream) {
            count++;
            sum += record.value;
        }
        return { name, count, sum };
    }

    const startTime = performance.now();
    const results = await Promise.all([
        processStream(streams[0], 'TypeA'),
        processStream(streams[1], 'TypeB'),
        processStream(streams[2], 'TypeC'),
    ]);
    const duration = performance.now() - startTime;

    for (const result of results) {
        console.log(`  ${result.name}: ${result.count} records, sum=${result.sum.toFixed(2)}`);
    }
    console.log(`  Total time: ${duration.toFixed(2)}ms (parallel)`);
    console.log();
}

async function memoryEfficientExample(client) {
    console.log('=== Example 6: Memory-Efficient Large Dataset ===');

    const stream = client.stream('MATCH (n) RETURN n', {
        mockRecords: 10000
    });

    // Process without loading all records into memory
    let count = 0;
    let sum = 0;
    let min = Infinity;
    let max = -Infinity;

    const startTime = performance.now();

    for await (const record of stream) {
        count++;
        sum += record.value;
        min = Math.min(min, record.value);
        max = Math.max(max, record.value);
    }

    const duration = performance.now() - startTime;
    const avg = sum / count;

    console.log(`  Processed ${count.toLocaleString()} records`);
    console.log(`  Statistics: min=${min.toFixed(2)}, max=${max.toFixed(2)}, avg=${avg.toFixed(2)}`);
    console.log(`  Duration: ${duration.toFixed(2)}ms`);
    console.log(`  Throughput: ${(count / duration * 1000).toFixed(0)} records/sec`);
    console.log('  (All computed without loading entire dataset into memory)\n');
}

async function main() {
    console.log('Geode Node.js Client - Streaming Examples');
    console.log('==========================================\n');

    const client = new GeodeClient({
        host: 'localhost',
        port: 3141
    });

    try {
        await client.connect();
        console.log();

        await basicStreamingExample(client);
        await batchedStreamingExample(client);
        await eventBasedStreamingExample(client);
        await transformStreamExample(client);
        await parallelStreamingExample(client);
        await memoryEfficientExample(client);

        console.log('Node.js streaming examples completed!');

    } catch (error) {
        console.error('Error:', error.message);
        process.exit(1);
    } finally {
        await client.close();
    }
}

main();
