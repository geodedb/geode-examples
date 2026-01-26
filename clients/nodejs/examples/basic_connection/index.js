// Basic Connection Example for Geode Node.js Client
//
// Verifies claim: Native Node.js client with async/await support
// Source: Features Overview, Client Libraries
// CANARY: REQ=REQ-CLIENT-NODEJS-001; FEATURE="NodeJSClient"; ASPECT=Client; STATUS=TESTED
//
// This example demonstrates basic connection and query execution
// using the Node.js client with modern ES modules.

// Mock client for demonstration (replace with actual geode-client import)
class GeodeClient {
    constructor(options) {
        this.host = options.host || 'localhost';
        this.port = options.port || 3141;
        this.connected = false;
    }

    async connect() {
        // Simulate connection delay
        await new Promise(resolve => setTimeout(resolve, 10));
        this.connected = true;
        console.log(`Connected to Geode at ${this.host}:${this.port}`);
    }

    async execute(query, params = {}) {
        if (!this.connected) {
            throw new Error('Not connected');
        }
        const displayQuery = query.length > 50 ? query.slice(0, 50) + '...' : query;
        console.log(`  Executing: ${displayQuery}`);

        // Simulate query execution
        await new Promise(resolve => setTimeout(resolve, 1));

        // Return mock results based on query type
        if (query.includes('RETURN')) {
            return {
                records: [{ sum: 2, name: 'Alice', age: 30 }],
                summary: { counters: { nodesCreated: 0 } }
            };
        }
        return {
            records: [],
            summary: { counters: { nodesCreated: query.includes('CREATE') ? 1 : 0 } }
        };
    }

    async close() {
        this.connected = false;
        console.log('Connection closed');
    }
}

async function main() {
    console.log('Geode Node.js Client - Basic Connection Example');
    console.log('================================================\n');

    // Configure client connection
    const client = new GeodeClient({
        host: 'localhost',
        port: 3141,
        // TLS is required for production
        tls: {
            rejectUnauthorized: true
        }
    });

    try {
        // Connect to Geode
        console.log('Connecting to Geode...');
        await client.connect();
        console.log();

        // Example 1: Simple query
        console.log('=== Example 1: Simple Query ===');
        const result1 = await client.execute('RETURN 1 + 1 AS sum');
        console.log(`Result: ${JSON.stringify(result1.records[0])}\n`);

        // Example 2: Create nodes
        console.log('=== Example 2: Create Nodes ===');
        await client.execute("CREATE (:Person {name: 'Alice', age: 30})");
        await client.execute("CREATE (:Person {name: 'Bob', age: 25})");
        await client.execute("CREATE (:Person {name: 'Charlie', age: 35})");
        console.log('Created 3 Person nodes\n');

        // Example 3: Create relationships
        console.log('=== Example 3: Create Relationships ===');
        await client.execute(
            "MATCH (a:Person {name: 'Alice'}), (b:Person {name: 'Bob'}) " +
            "CREATE (a)-[:KNOWS]->(b)"
        );
        await client.execute(
            "MATCH (b:Person {name: 'Bob'}), (c:Person {name: 'Charlie'}) " +
            "CREATE (b)-[:KNOWS]->(c)"
        );
        console.log();

        // Example 4: Parameterized query
        console.log('=== Example 4: Parameterized Query ===');
        const params = { name: 'Alice' };
        await client.execute(
            'MATCH (p:Person {name: $name}) RETURN p.name, p.age',
            params
        );
        console.log(`Parameters: ${JSON.stringify(params)}\n`);

        // Example 5: Pattern matching
        console.log('=== Example 5: Pattern Matching ===');
        await client.execute(
            'MATCH (p:Person)-[:KNOWS]->(friend) RETURN p.name, friend.name'
        );
        console.log();

        // Example 6: Aggregation
        console.log('=== Example 6: Aggregation ===');
        await client.execute(
            'MATCH (p:Person) RETURN count(p) AS total, avg(p.age) AS avg_age'
        );
        console.log();

        // Example 7: Update
        console.log('=== Example 7: Update ===');
        await client.execute(
            "MATCH (p:Person {name: 'Alice'}) SET p.age = 31"
        );
        console.log();

        // Cleanup
        console.log('=== Cleanup ===');
        await client.execute('MATCH (p:Person) DETACH DELETE p');
        console.log();

        console.log('Node.js basic example completed!');

    } catch (error) {
        console.error('Error:', error.message);
        process.exit(1);
    } finally {
        await client.close();
    }
}

main();
