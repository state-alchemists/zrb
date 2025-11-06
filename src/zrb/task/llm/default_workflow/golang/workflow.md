---
description: "A workflow for developing with Go, including project analysis and best practices."
---
# Go Development Guide

This guide provides the baseline for Go development. It is superseded by project-specific conventions.

## 1. Project Analysis Checklist

Before coding, inspect the project for these files to determine its conventions:

- **Module Information:** `go.mod` to identify the module path and dependencies. `go.sum` for dependency checksums.
- **Workspace:** `go.work` to see if the project is part of a multi-module workspace.
- **Tooling:** A `Makefile` is common for defining build, test, and lint commands.
- **CI/CD Configuration:** Files like `.github/workflows/go.yml` can reveal the exact commands used for verification.
- **Linting Config:** `.golangci.yml` defines the linting rules for `golangci-lint`.
- **Package Structure:** Analyze the `pkg/` and `internal/` directories to understand the project's layout.

## 2. Core Principles

- **Formatting:** `go fmt` is mandatory. All code must be formatted before committing.
- **Linting:** Adhere to the project's `golangci-lint` configuration. If none exists, use a sensible default.
- **Package Naming:** Use short, concise, all-lowercase package names.
- **Simplicity:** Write clear, simple, and readable code. Avoid unnecessary complexity or "clever" tricks.

## 3. Project Structure

- **`cmd/`:** Main applications for the project. Each subdirectory is a separate command.
- **`pkg/`:** Library code that's okay to be used by external applications.
- **`internal/`:** Private application and library code. It's not importable by other projects.

## 4. Implementation Patterns

- **Error Handling:** Match the existing error handling strategy. Check if the project uses a library like `pkg/errors` for wrapping or if it relies on the standard library's `fmt.Errorf` with `%w`.
- **Testing:** Replicate the existing test structure. Use table-driven tests if they are prevalent in the codebase. Place tests in `_test.go` files within the same package.
- **Concurrency:** Follow existing concurrency patterns. Pay close attention to how goroutines, channels, and mutexes are used.
- **Debugging:** Use the `delve` debugger for debugging Go applications.

## 5. Common Commands

- **Tidy Dependencies:** `go mod tidy`
- **Formatting:** `go fmt ./...`
- **Linting:** `golangci-lint run`
- **Testing:** `go test ./...`
- **Building:** `go build ./...`
- **Run:** `go run ./cmd/my-app`