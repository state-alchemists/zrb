---
description: "A workflow for developing with Rust, including project analysis and best practices."
---
# Rust Development Guide

This guide provides the baseline for Rust development. It is superseded by project-specific conventions.

## 1. Project Analysis Checklist

Before coding, inspect the project for these files to determine its conventions:

- **Crate & Dependency Info:** `Cargo.toml` is the source of truth for dependencies, features, and workspace members. `Cargo.lock` pins dependency versions.
- **Toolchain Version:** A `rust-toolchain.toml` file specifies the exact Rust version and components.
- **Formatting Config:** `rustfmt.toml` or ` .rustfmt.toml` defines the formatting rules.
- **Linting Config:** `clippy.toml` or the `[lints]` section in `Cargo.toml` defines Clippy rules.
- **Module Structure:** Analyze `src/lib.rs`, `src/main.rs`, and the `src/bin` directory to understand the crate structure and module hierarchy.

## 2. Core Principles

- **Formatting:** `cargo fmt` is mandatory. All code must be formatted.
- **Linting:** `cargo clippy` is mandatory. All warnings must be addressed. Strictly adhere to the project's Clippy configuration.
- **Safety:** Write safe Rust. `unsafe` blocks are forbidden unless you have an extremely compelling, documented reason and receive explicit approval.
- **Idiomatic Rust:** Embrace Rust's core features:
  - Use `Result` and `Option` for error and optional value handling.
  - Leverage ownership, borrowing, and lifetimes correctly.
  - Use iterators and closures over manual loops where it improves clarity.

## 3. Implementation Patterns

- **Error Handling:** Match the existing error handling strategy. If the project uses a specific error library (e.g., `anyhow`, `thiserror`), you must use it.
- **Testing:** Place unit tests in a `#[cfg(test)]` module at the bottom of the file they are testing. Integration tests go in the `tests/` directory. Follow existing patterns for test setup.
- **API Design:** Follow the Rust API Guidelines. Pay attention to how public APIs are structured and documented.

## 4. Common Commands

- **Formatting:** `cargo fmt`
- **Linting:** `cargo clippy -- -D warnings` (Treat all warnings as errors)
- **Testing:** `cargo test`
- **Building:** `cargo build`
- **Run:** `cargo run`
- **Check for Errors:** `cargo check` (Faster than a full build)
