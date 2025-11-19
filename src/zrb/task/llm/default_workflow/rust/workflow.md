---
description: "A workflow for developing with Rust, including project analysis and best practices."
---
Follow this workflow to deliver safe, efficient, and idiomatic Rust code that respects project conventions.

# Core Mandates

- **Memory Safety:** Leverage Rust's ownership system for safe code
- **Zero-Cost Abstractions:** Use Rust's features without runtime overhead
- **Idiomatic Patterns:** Follow established Rust conventions and practices
- **Tool Integration:** Use Cargo and Rust tooling effectively

# Tool Usage Guideline
- Use `read_from_file` to analyze Cargo.toml and source code
- Use `search_files` to find Rust patterns and conventions
- Use `run_shell_command` for Cargo operations
- Use `list_files` to understand project structure

# Step 1: Project Analysis

1. **Crate Information:** Examine `Cargo.toml` for dependencies, features, and workspace members
2. **Toolchain Version:** Check `rust-toolchain.toml` for Rust version and components
3. **Formatting Configuration:** Look for `rustfmt.toml` or `.rustfmt.toml`
4. **Linting Configuration:** Check `clippy.toml` or `[lints]` section in `Cargo.toml`
5. **Module Structure:** Analyze `src/lib.rs`, `src/main.rs`, and `src/bin/` directory
6. **Workspace Configuration:** Check for workspace members in `Cargo.toml`

# Step 2: Understand Conventions

1. **Formatting:** `cargo fmt` is mandatory for all code
2. **Linting:** `cargo clippy` must pass with project configuration
3. **Safety:** Avoid `unsafe` blocks unless absolutely necessary and documented
4. **Error Handling:** Follow project's error handling strategy (anyhow, thiserror, etc.)
5. **Testing:** Use established test patterns and organization

# Step 3: Implementation Planning

1. **Type Design:** Plan structs, enums, and traits based on project patterns
2. **Ownership Strategy:** Consider ownership, borrowing, and lifetime requirements
3. **Error Handling:** Plan appropriate error types and handling
4. **Concurrency:** Consider async/await or threading requirements
5. **Testing Strategy:** Plan comprehensive unit and integration tests

# Step 4: Write Code

## Code Quality Standards
- **Formatting:** All code must be `cargo fmt` compliant
- **Linting:** Address all `cargo clippy` warnings
- **Documentation:** Add rustdoc comments for public APIs
- **Naming:** Follow Rust naming conventions (snake_case for variables/functions, PascalCase for types)
- **Safety:** Write safe Rust without unnecessary `unsafe` blocks

## Rust Idioms
- **Result and Option:** Use for error and optional value handling
- **Ownership System:** Leverage borrowing and lifetimes correctly
- **Iterators:** Prefer iterator methods over manual loops
- **Pattern Matching:** Use `match` and `if let` for control flow
- **Traits:** Use for polymorphism and code organization

# Step 5: Testing and Verification

1. **Write Tests:** Create comprehensive tests using `#[cfg(test)]` modules
2. **Run Tests:** Execute `cargo test` to verify functionality
3. **Format Code:** Run `cargo fmt` to ensure proper formatting
4. **Lint Code:** Run `cargo clippy -- -D warnings` to catch issues
5. **Build Verification:** Run `cargo check` for fast compilation checking

# Step 6: Quality Assurance

## Testing Standards
- **Unit Tests:** Place in `#[cfg(test)]` modules within source files
- **Integration Tests:** Create in `tests/` directory for crate-level testing
- **Documentation Tests:** Include examples in rustdoc comments
- **Property Testing:** Use proptest or quickcheck for comprehensive testing

## Code Review Checklist
- [ ] Code follows project formatting standards
- [ ] All tests pass with good coverage
- [ ] No clippy warnings
- [ ] Error handling is appropriate and idiomatic
- [ ] Documentation is complete for public APIs
- [ ] Performance considerations addressed
- [ ] Memory safety verified

# Step 7: Cargo Operations

## Development Commands
- `cargo check`: Fast compilation checking
- `cargo build`: Build the project
- `cargo run`: Build and run the project
- `cargo test`: Run all tests
- `cargo fmt`: Format code
- `cargo clippy`: Run linter

## Dependency Management
- `cargo add <dependency>`: Add a new dependency
- `cargo update`: Update dependencies
- `cargo tree`: Show dependency tree
- `cargo audit`: Check for security vulnerabilities

# Step 8: Advanced Rust Features

## Async/Await
- **Async Runtime:** Use tokio, async-std, or smol based on project
- **Futures:** Understand and use futures appropriately
- **Concurrency:** Use channels and synchronization primitives

## Macros
- **Declarative Macros:** Use for code generation when appropriate
- **Procedural Macros:** Use for advanced metaprogramming
- **Attribute Macros:** Use for annotations and code transformation

## Unsafe Code (Use Sparingly)
- **FFI:** For foreign function interface
- **Memory Management:** For low-level memory operations
- **Performance Optimization:** Only when measurements justify
- **Documentation:** Must document safety invariants

# Step 9: Finalize and Deliver

1. **Verify Dependencies:** Ensure dependency versions are appropriate
2. **Run Full Test Suite:** Verify all existing tests still pass
3. **Security Audit:** Run `cargo audit` for security vulnerabilities
4. **Performance Testing:** Benchmark critical code paths if applicable
5. **Documentation:** Generate and verify rustdoc documentation

# Common Patterns

## Error Handling
- **thiserror:** For defining custom error types
- **anyhow:** For application-level error handling
- **Result Propagation:** Use `?` operator appropriately

## Concurrency
- **std::thread:** For CPU-bound parallelism
- **tokio::spawn:** For async task spawning
- **std::sync:** For synchronization primitives
- **crossbeam:** For advanced concurrency patterns

## Performance
- **Profiling:** Use perf, flamegraph, or cargo instruments
- **Benchmarking:** Use criterion for reliable benchmarks
- **Optimization:** Focus on measured bottlenecks

# Risk Assessment Guidelines

## Low Risk (Proceed Directly)
- Adding tests to existing test modules
- Implementing utility functions following established patterns
- Creating new modules in established patterns

## Moderate Risk (Explain and Confirm)
- Modifying core data structures
- Changing public trait implementations
- Adding new dependencies
- Using `unsafe` blocks

## High Risk (Refuse and Explain)
- Breaking memory safety guarantees
- Modifying critical system components
- Changes affecting multiple crates in workspace
- Operations that could introduce security vulnerabilities