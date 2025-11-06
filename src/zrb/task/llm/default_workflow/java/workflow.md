---
description: "A workflow for developing with Java, including project analysis and best practices."
---
# Java Development Guide

This guide provides the baseline for Java development. It is superseded by project-specific conventions.

## 1. Project Analysis Checklist

Before coding, inspect the project for these files to determine its conventions:

- **Build System:** `pom.xml` (Maven) or `build.gradle` (Gradle). Note the dependencies, plugins, and build lifecycle.
- **Java Version:** Look for a `.java-version` file, or check the `pom.xml` or `build.gradle` file.
- **Style & Linting Config:** `.checkstyle.xml`, `.pmd.xml`. These define the coding standard.
- **Testing Framework:** Look for a `src/test/java` directory and check the build file for dependencies like `junit` or `testng`.

## 2. Core Principles

- **Style:** Strictly adhere to the project's configured linter (e.g., Checkstyle, PMD). If none exist, default to the Google Java Style Guide.
- **Object-Oriented Design:** Follow SOLID principles and use design patterns where appropriate.
- **API Design:** Follow the principles of good API design, such as keeping APIs small and focused.

## 3. Implementation Patterns

- **Error Handling:** Replicate existing patterns for exceptions. Use checked exceptions for recoverable errors and unchecked exceptions for programming errors.
- **Testing:** Use the project's existing test structure. Write unit tests for all new code.
- **Concurrency:** Follow existing concurrency patterns. Use the `java.util.concurrent` package for high-level concurrency abstractions.

## 4. Common Commands

- **Maven:**
  - **Clean:** `mvn clean`
  - **Compile:** `mvn compile`
  - **Test:** `mvn test`
  - **Package:** `mvn package`
  - **Install:** `mvn install`
- **Gradle:**
  - **Clean:** `./gradlew clean`
  - **Build:** `./gradlew build`
  - **Test:** `./gradlew test`
