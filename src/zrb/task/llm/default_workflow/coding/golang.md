# Go Development Guide

## Core Principles
- **Follow Go conventions** and effective Go patterns
- **Use `go fmt`** for consistent formatting
- **Follow project's package structure** and naming

## Project Analysis
- Check for: `go.mod`, `go.sum`, `Makefile`
- Look for project-specific patterns in existing code
- Identify testing approach: table tests, integration tests

## Implementation Patterns
- **Error Handling:** Follow project's error wrapping and handling style
- **Package Organization:** Match existing package boundaries and dependencies
- **Naming:** Follow Go conventions (camelCase, short names)
- **Testing:** Use same test organization and helper patterns

## Common Commands
- Formatting: `go fmt`
- Testing: `go test`
- Linting: `golangci-lint`, `staticcheck`
- Building: `go build`