// Command transaction_pipelining validates the "why-quic-matters" post's
// "Transaction Pipelining" example from the "Geode-Specific Benefits"
// section.
//
// The post's original snippet calls `client.Begin()` / `tx.Execute(...)` /
// `tx.Commit()`. That is not the real `database/sql` interface this driver
// implements -- `sql.DB` has no `Begin` receiver in that form and
// `sql.Tx` has no `Execute` method at all (capital E). The real interface
// is the standard library's own: `db.Begin()` / `tx.Exec(...)` /
// `tx.Commit()`. See ../FINDINGS.md for the full story.
package main

import (
	"database/sql"
	"fmt"
	"log"
	"os"

	_ "geodedb.com/geode"
)

func main() {
	dsn := fmt.Sprintf("quic://%s:%s?insecure_tls_skip_verify=true&user=%s&pass=%s",
		os.Getenv("GEODE_HOST"), os.Getenv("GEODE_PORT"), os.Getenv("GEODE_USER"), os.Getenv("GEODE_PASSWORD"))

	db, err := sql.Open("geode", dsn)
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()

	tx, err := db.Begin()
	if err != nil {
		log.Fatal(err)
	}

	if _, err := tx.Exec("CREATE (:User {id: 101})"); err != nil {
		tx.Rollback()
		log.Fatal(err)
	}
	if _, err := tx.Exec("CREATE (:User {id: 102})"); err != nil {
		tx.Rollback()
		log.Fatal(err)
	}
	if _, err := tx.Exec("MATCH (u1:User {id: 101}), (u2:User {id: 102}) CREATE (u1)-[:KNOWS]->(u2)"); err != nil {
		tx.Rollback()
		log.Fatal(err)
	}

	if err := tx.Commit(); err != nil {
		log.Fatal(err)
	}
	fmt.Println("OK: transaction committed")
}
