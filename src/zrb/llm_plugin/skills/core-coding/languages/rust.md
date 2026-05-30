# Rust Guide

## Manifest & Layout

- **Manifest**: `Cargo.toml` (deps + metadata); `Cargo.lock` (lockfile — commit for binaries, optional for libraries)
- **Source**: `src/` — `src/main.rs` for a binary, `src/lib.rs` for a library
- **Tests**: unit tests inline (`#[cfg(test)] mod tests`); integration tests in `tests/`
- **Rust edition**: read `[package] edition` in `Cargo.toml` — 2021 is current

## Idioms

- **`Result<T, E>` for fallible operations, `Option<T>` for absence.** Use `?` to propagate, `match`/`if let` to handle.
- **Iterators over loops.** `.iter().map(...).filter(...).collect()` reads better and often optimizes better than a manual `for` loop.
- **Borrow before clone.** `fn f(s: &str)` over `fn f(s: String)` unless you genuinely need ownership.
- **Newtypes for invariants.** `struct UserId(u64)` over a bare `u64` when the value has a domain meaning.
- **`derive` the obvious traits.** `#[derive(Debug, Clone, PartialEq)]` — explicit is better than magical.
- **`anyhow::Result` in binaries, custom error enums in libraries.** Libraries shouldn't force `anyhow` on callers.

## Common Anti-Patterns

- **Cloning to escape the borrow checker.** Sometimes correct; usually a sign you're fighting the design. Pause and rethink ownership.
- **`unwrap()` and `expect()` in production code.** Fine in tests and prototypes; in production, propagate with `?` or handle explicitly.
- **`Box<dyn Error>` as a return type in libraries.** Hides the actual error types from callers.
- **Excessive lifetimes on every signature.** Most function signatures don't need explicit lifetimes — let elision work.
- **`.collect::<Vec<_>>()` followed immediately by `.iter()`.** Skip the round trip — chain the iterators directly.
- **`if let Some(x) = ... { ... } else { panic!() }`.** Just `let x = ....unwrap()` or `?` — same effect, less code.

## Complexity Budget Notes

- Function length ≤30 lines: pattern matches (`match`) can be long but cohesive. If each arm is a one-liner, the whole `match` reads as a table — don't split mechanically.
- Parameters ≤4: lifetimes don't count toward this. Generic parameters (`<T: Trait>`) count as part of the signature surface but not toward the limit.
- Nesting ≤2: prefer `?` over nested `match`/`if let`. Use `.and_then()`/`.map()` for chains.

## Tests

- **Framework**: stdlib `#[test]`; `cargo test` runs everything
- **Naming**: `fn test_should_<behavior>_when_<condition>()` inside `#[cfg(test)] mod tests`
- **Run**: `cargo test` (all); `cargo test --lib` (library only); `cargo test --release` (optimized — for benchmarks)
- **Property tests**: `proptest` or `quickcheck` for invariants over inputs

## Lint, Format

- **Format**: `cargo fmt --check` (`--write` to apply) — config in `rustfmt.toml` if any
- **Lint**: `cargo clippy --all-targets -- -D warnings` — `-D warnings` treats lints as errors
- **Check**: `cargo check` — type-checks without building; fast feedback during development

## Canonical Verify Sequence

```bash
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test
cargo build --release         # binaries only; skip for libraries
```
