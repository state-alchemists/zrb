# Kotlin Development Guide

This guide provides the baseline for Kotlin development. It is superseded by project-specific conventions.

## 1. Project Analysis Checklist

Before coding, inspect the project for these files to determine its conventions:

- **Build System:** `build.gradle.kts` (Gradle with Kotlin DSL) or `pom.xml` (Maven). Note the dependencies, plugins, and build lifecycle.
- **Kotlin Version:** Look for a `.kotlin-version` file, or check the `build.gradle.kts` or `pom.xml` file.
- **Style & Linting Config:** `.editorconfig`, `.ktlint.ruleset.json`. These define the coding standard.
- **Testing Framework:** Look for a `src/test/kotlin` directory and check the build file for dependencies like `junit` or `kotest`.

## 2. Core Principles

- **Style:** Strictly adhere to the project's configured linter (e.g., `ktlint`). If none exists, default to the official Kotlin coding conventions.
- **Idiomatic Kotlin:** Embrace Kotlin's core features:
  - Use `val` and `var` correctly.
  - Use null safety features (`?`, `!!`, `let`).
  - Use data classes for immutable data.
  - Use extension functions to add functionality to existing classes.
- **Functional Programming:** Use higher-order functions, lambdas, and collections API where it improves clarity.

## 3. Implementation Patterns

- **Error Handling:** Replicate existing patterns for exceptions. Use `try-catch` expressions and the `Result` type.
- **Testing:** Use the project's existing test structure. Write unit tests for all new code.
- **Coroutines:** Follow existing concurrency patterns. Use coroutines for asynchronous programming.

## 4. Common Commands

- **Gradle:**
    - **Clean:** `./gradlew clean`
    - **Build:** `./gradlew build`
    - **Test:** `./gradlew test`
- **Maven:**
    - **Clean:** `mvn clean`
    - **Compile:** `mvn compile`
    - **Test:** `mvn test`
    - **Package:** `mvn package`
    - **Install:** `mvn install`
