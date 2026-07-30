// Package main runs the two operations from the "Introducing Geode" blog
// post's Getting Started section, using the Go database/sql driver shown
// in the post's "Native Language Support" section.
//
// The post's own DSN example (`quic://localhost:3141`) has no TLS or auth
// parameters. Against a real server that requires TLS verification opt-out
// for a self-signed dev cert and authenticates every connection, that DSN
// fails. See ../FINDINGS.md for the full story; this file uses the
// corrected DSN.
package main

import (
	"database/sql"
	"fmt"
	"log"
	"os"

	_ "geodedb.com/geode"
)

func main() {
	// NOTE on encoding: GEODE_USER/GEODE_PASSWORD are interpolated raw here,
	// unlike nodejs/index.mjs's encodeURIComponent() calls. This is safe for
	// this driver specifically: the Go client's own DSN parser splits on the
	// literal `&`/`=` delimiters without running the query string through a
	// standards-strict net/url-style percent-decoder first, so an unescaped
	// space in GEODE_PASSWORD (the shared dev password is a multi-word
	// passphrase, see ../_shared/bootstrap.sh) passes through intact rather
	// than truncating or erroring -- confirmed by this file actually
	// authenticating successfully against the live container. This is a
	// property of *this* client's parser, not a general rule; do not assume
	// other DSN-based clients will tolerate unescaped reserved characters
	// (Node.js's README-documented userinfo form, for one, needs
	// encodeURIComponent -- see FINDINGS.md).
	dsn := fmt.Sprintf("quic://%s:%s?insecure_tls_skip_verify=true&user=%s&pass=%s",
		mustEnv("GEODE_HOST"), mustEnv("GEODE_PORT"), mustEnv("GEODE_USER"), mustEnv("GEODE_PASSWORD"))

	db, err := sql.Open("geode", dsn)
	if err != nil {
		log.Fatalf("sql.Open: %v", err)
	}
	defer db.Close()

	if _, err := db.Exec("CREATE (:Person {name: 'Alice', age: 30})"); err != nil {
		log.Fatalf("CREATE failed: %v", err)
	}

	rows, err := db.Query("MATCH (p:Person) RETURN p")
	if err != nil {
		log.Fatalf("MATCH failed: %v", err)
	}
	defer rows.Close()

	count := 0
	for rows.Next() {
		count++
	}
	if err := rows.Err(); err != nil {
		log.Fatalf("row iteration failed: %v", err)
	}
	fmt.Printf("OK: %d Person node(s) returned\n", count)
}

func mustEnv(k string) string {
	v := envOrEmpty(k)
	if v == "" {
		panic("missing required env var: " + k)
	}
	return v
}

func envOrEmpty(k string) string {
	return os.Getenv(k)
}
