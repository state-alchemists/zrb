---
description: "A workflow for developing with Go, including project analysis and best practices."
---
Follow this workflow to deliver high-quality, idiomatic Go code that respects project conventions.

# Core Mandates

- **Simplicity First:** Write clear, simple, and readable code
- **Idiomatic Go:** Follow Go conventions and community standards
- **Tool Integration:** Leverage Go's excellent tooling ecosystem
- **Safety and Reliability:** Write robust, well-tested code

# Tool Usage Guideline
- Use `read_from_file` to analyze Go modules and configuration
- Use `search_files` to find Go patterns and conventions
- Use `run_shell_command` for Go toolchain operations
- Use `list_files` to understand project structure

# Step 1: Project Analysis

1. **Module Information:** Examine `go.mod` for module path and dependencies
2. **Workspace:** Check for `go.work` for multi-module workspace configuration
3. **Tooling:** Look for `Makefile` with build, test, and lint commands
4. **CI/CD Configuration:** Check `.github/workflows/go.yml` for verification commands
5. **Linting Config:** Examine `.golangci.yml` for linting rules
6. **Package Structure:** Analyze `pkg/`, `internal/`, and `cmd/` directories

# Step 2: Understand Conventions

1. **Formatting:** `go fmt` is mandatory for all code
2. **Linting:** Adhere to project's `golangci-lint` configuration
3. **Package Naming:** Use short, concise, all-lowercase package names
4. **Error Handling:** Match existing error handling patterns
5. **Testing:** Follow established test structure and patterns

# Step 3: Implementation Planning

1. **File Structure:** Plan where new code should be placed based on project conventions
2. **Dependencies:** Identify if new dependencies are needed and verify they're appropriate
3. **API Design:** Consider how new code integrates with existing APIs
4. **Testing Strategy:** Plan comprehensive tests for new functionality

# Step 4: Write Code

## Code Quality Standards
- **Formatting:** All code must be `go fmt` compliant
- **Linting:** Address all `golangci-lint` warnings
- **Naming:** Follow Go naming conventions (camelCase for variables, PascalCase for exports)
- **Documentation:** Add godoc comments for exported functions and types

## Implementation Patterns
- **Error Handling:** Use appropriate error wrapping based on project patterns
- **Concurrency:** Follow existing goroutine and channel usage patterns
- **Interfaces:** Define small, focused interfaces
- **Composition:** Prefer composition over inheritance

# Step 5: Testing and Verification

1. **Write Tests:** Create comprehensive tests for all new functionality
2. **Run Tests:** Execute `go test ./...` to verify functionality
3. **Format Code:** Run `go fmt ./...` to ensure proper formatting
4. **Lint Code:** Run `golangci-lint run` to catch issues
5. **Build Verification:** Run `go build ./...` to ensure code compiles

# Step 6: Quality Assurance

## Testing Standards
- **Table-Driven Tests:** Use for comprehensive test coverage
- **Test Files:** Place tests in `_test.go` files within the same package
- **Benchmarks:** Add benchmarks for performance-critical code
- **Examples:** Include example code in documentation

## Code Review Checklist
- [ ] Code follows project formatting standards
- [ ] All tests pass
- [ ] No linting warnings
- [ ] Error handling is appropriate
- [ ] Documentation is complete
- [ ] Performance considerations addressed

# Step 7: Finalize and Deliver

1. **Verify Dependencies:** Run `go mod tidy` to clean up dependencies
2. **Run Full Test Suite:** Ensure all existing tests still pass
3. **Document Changes:** Update relevant documentation
4. **Prepare for Review:** Ensure code is ready for team review

# Common Commands Reference

## Development
- `go fmt ./...`: Format all Go code
- `go vet ./...`: Report suspicious constructs
- `go build ./...`: Build all packages
- `go run ./cmd/my-app`: Run a specific application

## Testing
- `go test ./...`: Run all tests
- `go test -v ./...`: Run tests with verbose output
- `go test -race ./...`: Run tests with race detector
- `go test -bench=. ./...`: Run benchmarks

## Dependency Management
- `go mod tidy`: Add missing and remove unused modules
- `go mod download`: Download modules to local cache
- `go list -m all`: List all dependencies
- `go get package@version`: Add or update a dependency

## Debugging
- `dlv debug`: Debug with Delve
- `go tool pprof`: Performance profiling
- `go tool trace`: Execution tracing

# Risk Assessment Guidelines

## Low Risk (Proceed Directly)
- Reading configuration files
- Running tests and linters
- Adding tests to existing packages

## Moderate Risk (Explain and Confirm)
- Adding new dependencies
- Modifying core business logic
- Changing public API interfaces

## High Risk (Refuse and Explain)
- Modifying critical system paths
- Operations that could break the build
- Changes that affect multiple teams