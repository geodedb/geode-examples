//! Runs the two operations from the "Introducing Geode" blog post's Getting
//! Started section, using the Rust client shown in the post's "Native
//! Language Support" section.
//!
//! The post's own snippet (`Client::connect("quic://localhost:3141").await?`)
//! does not exist on the real (alpha) client -- there is no `Client::connect`
//! associated function, and no TLS/auth params. See ../FINDINGS.md for the
//! full story; this file uses the real builder API instead.
//!
//! The builder API (rather than `Client::from_dsn` with `user:pass@host` in
//! the URL) is used deliberately: the shared dev password contains spaces
//! (see bootstrap.sh), which would need percent-encoding in a DSN userinfo
//! component. `.username()/.password()` take plain strings, so there's
//! nothing to encode.

use geode_client::{Client, Result};

#[tokio::main]
async fn main() -> Result<()> {
    let host = std::env::var("GEODE_HOST").expect("GEODE_HOST must be set");
    let port: u16 = std::env::var("GEODE_PORT")
        .expect("GEODE_PORT must be set")
        .parse()
        .expect("GEODE_PORT must be numeric");
    let user = std::env::var("GEODE_USER").expect("GEODE_USER must be set");
    let pass = std::env::var("GEODE_PASSWORD").expect("GEODE_PASSWORD must be set");

    let client = Client::new(&host, port)
        .skip_verify(true)
        .username(user)
        .password(pass);

    let mut conn = client.connect().await?;

    conn.query("CREATE (:Person {name: 'Alice', age: 30})")
        .await?;

    let (page, _) = conn.query("MATCH (p:Person) RETURN p").await?;
    println!("OK: {} Person node(s) returned", page.rows.len());

    conn.close()?;
    Ok(())
}
