# Rust Development Guide

## Core Principles
- **Follow Rust conventions** and idiomatic patterns
- **Use `rustfmt`** for consistent formatting
- **Follow ownership and borrowing** patterns in existing code

## Project Analysis
- Check for: `Cargo.toml`, `Cargo.lock`
- Look for: `rustfmt.toml`, `clippy.toml`
- Identify testing approach: unit tests, integration tests

## Implementation Patterns
- **Error Handling:** Follow project's `Result` and `Option` patterns
- **Crate Organization:** Match existing module structure
- **Ownership:** Follow existing borrowing and lifetime patterns
- **Testing:** Use same test organization and attribute patterns

## Common Commands
- Formatting: `cargo fmt`
- Testing: `cargo test`
- Linting: `cargo clippy`
- Building: `cargo build`