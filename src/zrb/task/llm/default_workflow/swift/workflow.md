# Swift Development Guide

This guide provides the baseline for Swift development. It is superseded by project-specific conventions.

## 1. Project Analysis Checklist

Before coding, inspect the project for these files to determine its conventions:

- **Project File:** `*.xcodeproj` or `Package.swift`. This defines the project structure, dependencies, and build settings.
- **Swift Version:** Look for a `.swift-version` file.
- **Style & Linting Config:** `.swiftlint.yml`. This defines the coding standard.
- **Testing Framework:** Look for a `*Tests` directory and check the project file for dependencies like `XCTest`.

## 2. Core Principles

- **Style:** Strictly adhere to the project's configured linter (e.g., SwiftLint). If none exists, default to the Swift API Design Guidelines.
- **Idiomatic Swift:** Embrace Swift's core features:
  - Use `let` and `var` correctly.
  - Use optionals (`?`, `!`) for null safety.
  - Use structs for value types and classes for reference types.
  - Use protocols and extensions to build flexible and extensible code.
- **Memory Management:** Understand and use Automatic Reference Counting (ARC).

## 3. Implementation Patterns

- **Error Handling:** Replicate existing patterns for error handling. Use `try-catch` and the `Result` type.
- **Testing:** Use the project's existing test structure. Write unit tests for all new code.
- **Concurrency:** Follow existing concurrency patterns. Use Grand Central Dispatch (GCD) and `async/await`.

## 4. Common Commands

- **Swift Package Manager (SPM):**
  - **Update Dependencies:** `swift package update`
  - **Build:** `swift build`
  - **Test:** `swift test`
- **Xcode:**
  - **Build:** `xcodebuild build`
  - **Test:** `xcodebuild test`
