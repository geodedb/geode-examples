// Command social_network validates the "Building a Social Network with
// Geode" post's Go `SocialNetwork` struct ("Step 5: Application Code" ->
// "Go Example").
//
// Two things adapted from the post, both documented in ../FINDINGS.md:
//
//  1. Auth: the post's `main()` calls
//     `NewSocialNetwork("quic://localhost:3141")` with no credentials at
//     all -- same missing-auth problem as the post's Python example.
//     The confirmed-working fix (same pattern used throughout this repo,
//     e.g. why-quic-matters/go/transaction_pipelining.go): embed
//     `user=`/`pass=` in the DSN query string.
//
//  2. Placeholders: the post uses `$1`/`$2`/`$3`/`$4` positional
//     placeholders. **Confirmed live, that style does NOT work** with
//     plain positional args -- `db.Exec` fails with:
//       geode: 22023: Positional parameter out of range (referenced a
//       parameter that was not supplied)
//     Reading the driver source (conn.go's rewritePlaceholders) explains
//     why: it inlines `?` characters client-side by ordinal, but only
//     forwards *named* args (`sql.Named(...)`) into the server-side
//     params map for `$name` resolution. Plain positional args passed to
//     `db.Exec(query, v1, v2, ...)` have no Name, so a `$1`/`$2` query
//     text is sent to the server with an empty params map and the
//     server can't resolve it. The Go client README's own example
//     (`db.PrepareContext(ctx, "MATCH (n:Person {name: ?}) RETURN n")`)
//     uses `?`, and this file now does too -- confirmed live: `?`
//     resolves correctly and the written data round-trips as expected.
//     See ../FINDINGS.md for the full writeup; this corrects the
//     "$N works" assumption carried in from Tasks 2-3, which never
//     actually exercised a placeholder with a real bound parameter.
package main

import (
	"database/sql"
	"fmt"
	"log"
	"os"

	_ "geodedb.com/geode"
)

type SocialNetwork struct {
	db *sql.DB
}

func NewSocialNetwork(connStr string) (*SocialNetwork, error) {
	db, err := sql.Open("geode", connStr)
	if err != nil {
		return nil, err
	}
	return &SocialNetwork{db: db}, nil
}

func (sn *SocialNetwork) CreateUser(username, email, displayName, passwordHash string) error {
	_, err := sn.db.Exec(`
        CREATE (u:User {
            username: ?,
            email: ?,
            display_name: ?,
            password_hash: ?,
            created_at: timestamp()
        })
    `, username, email, displayName, passwordHash)
	return err
}

func (sn *SocialNetwork) CreatePost(username, content, visibility string) error {
	_, err := sn.db.Exec(`
        MATCH (u:User {username: ?})
        CREATE (u)-[:POSTED {timestamp: timestamp()}]->(p:Post {
            content: ?,
            visibility: ?,
            created_at: timestamp()
        })
    `, username, content, visibility)
	return err
}

func (sn *SocialNetwork) AddFriend(user1, user2 string) error {
	_, err := sn.db.Exec(`
        MATCH (u1:User {username: ?})
        MATCH (u2:User {username: ?})
        CREATE (u1)-[:FRIENDS_WITH {since: timestamp()}]->(u2)
        CREATE (u2)-[:FRIENDS_WITH {since: timestamp()}]->(u1)
    `, user1, user2)
	return err
}

func main() {
	dsn := fmt.Sprintf("quic://%s:%s?insecure_tls_skip_verify=true&user=%s&pass=%s",
		os.Getenv("GEODE_HOST"), os.Getenv("GEODE_PORT"), os.Getenv("GEODE_USER"), os.Getenv("GEODE_PASSWORD"))

	sn, err := NewSocialNetwork(dsn)
	if err != nil {
		log.Fatal(err)
	}
	defer sn.db.Close()

	if err := sn.CreateUser("go_smoketest_alice", "go_alice@example.com", "Alice Go", "hash123"); err != nil {
		log.Fatal(err)
	}
	if err := sn.CreateUser("go_smoketest_bob", "go_bob@example.com", "Bob Go", "hash456"); err != nil {
		log.Fatal(err)
	}
	if err := sn.CreatePost("go_smoketest_alice", "Hello from Go!", "public"); err != nil {
		log.Fatal(err)
	}
	if err := sn.AddFriend("go_smoketest_alice", "go_smoketest_bob"); err != nil {
		log.Fatal(err)
	}
	fmt.Println("OK: CreateUser + CreatePost + AddFriend succeeded")
}
