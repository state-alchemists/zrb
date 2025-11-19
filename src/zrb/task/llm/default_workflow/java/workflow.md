---
description: "A workflow for developing with Java, including project analysis and best practices."
---
Follow this workflow to deliver robust, maintainable Java code that follows project conventions.

# Core Mandates

- **Object-Oriented Excellence:** Follow SOLID principles and design patterns
- **Type Safety:** Leverage Java's strong typing system
- **Tool Integration:** Use Maven/Gradle and IDE tools effectively
- **Enterprise Standards:** Follow established Java enterprise patterns

# Tool Usage Guideline
- Use `read_from_file` to analyze build configurations and source code
- Use `search_files` to find Java patterns and conventions
- Use `run_shell_command` for build and test operations
- Use `list_files` to understand project structure

# Step 1: Project Analysis

1. **Build System:** Examine `pom.xml` (Maven) or `build.gradle` (Gradle)
2. **Java Version:** Check `.java-version` or build configuration
3. **Style Configuration:** Look for `.checkstyle.xml`, `.pmd.xml`, `.editorconfig`
4. **Testing Framework:** Analyze `src/test/java` and test dependencies
5. **Project Structure:** Understand package organization and module boundaries
6. **Dependencies:** Review dependency management and versioning

# Step 2: Understand Conventions

1. **Code Style:** Adhere to project's configured linter (Checkstyle, PMD)
2. **Package Organization:** Follow established package naming and structure
3. **Class Design:** Use appropriate design patterns and principles
4. **Exception Handling:** Follow project's exception handling strategy
5. **Testing Patterns:** Use established test frameworks and patterns

# Step 3: Implementation Planning

1. **Class Structure:** Plan new classes and interfaces based on project patterns
2. **Package Placement:** Determine appropriate package for new code
3. **Dependencies:** Identify required dependencies and verify compatibility
4. **API Design:** Consider public interfaces and backward compatibility
5. **Testing Strategy:** Plan comprehensive unit and integration tests

# Step 4: Write Code

## Code Quality Standards
- **Formatting:** Follow project's code style configuration
- **Documentation:** Add Javadoc for public APIs and complex logic
- **Naming:** Use clear, descriptive names following Java conventions
- **Immutability:** Prefer immutable objects where appropriate
- **Composition:** Favor composition over inheritance

## Implementation Patterns
- **Exception Handling:** Use checked exceptions for recoverable errors, unchecked for programming errors
- **Collections:** Use appropriate collection types and avoid raw types
- **Streams:** Leverage Java Streams for functional-style operations
- **Optional:** Use `Optional` for nullable return values
- **Records:** Use records for data carrier classes (Java 14+)

# Step 5: Testing and Verification

1. **Write Unit Tests:** Create comprehensive tests for all new functionality
2. **Run Tests:** Execute `mvn test` or `gradle test` to verify functionality
3. **Static Analysis:** Run Checkstyle, PMD, or other configured linters
4. **Build Verification:** Ensure code compiles without warnings
5. **Integration Tests:** Add integration tests for cross-component functionality

# Step 6: Quality Assurance

## Testing Standards
- **Test Structure:** Follow project's test organization patterns
- **Mocking:** Use appropriate mocking frameworks (Mockito, etc.)
- **Assertions:** Use fluent assertion libraries (AssertJ, Hamcrest)
- **Coverage:** Aim for high test coverage of business logic

## Code Review Checklist
- [ ] Code follows project formatting standards
- [ ] All tests pass with good coverage
- [ ] No static analysis warnings
- [ ] Exception handling is appropriate
- [ ] Javadoc is complete for public APIs
- [ ] Performance considerations addressed
- [ ] Thread safety considered where needed

# Step 7: Build and Deployment

## Maven Commands
- `mvn clean`: Clean build artifacts
- `mvn compile`: Compile source code
- `mvn test`: Run unit tests
- `mvn package`: Create deployable package
- `mvn install`: Install to local repository
- `mvn verify`: Run integration tests

## Gradle Commands
- `./gradlew clean`: Clean build artifacts
- `./gradlew build`: Build and test
- `./gradlew test`: Run unit tests
- `./gradlew check`: Run all checks

# Step 8: Finalize and Deliver

1. **Verify Dependencies:** Ensure dependency versions are consistent
2. **Run Full Test Suite:** Verify all existing tests still pass
3. **Static Analysis:** Address any remaining linting issues
4. **Documentation:** Update relevant documentation and Javadoc
5. **Performance Testing:** Verify performance characteristics

# Advanced Java Features

## Modern Java (8+)
- **Lambdas:** Use for concise functional programming
- **Streams:** Process collections efficiently
- **Optional:** Handle null values safely
- **Modules:** Use Java Platform Module System (JPMS) if configured

## Concurrency
- **CompletableFuture:** For asynchronous programming
- **Executors:** Manage thread pools effectively
- **Concurrent Collections:** Use thread-safe collections
- **Synchronization:** Prefer higher-level concurrency utilities

## Enterprise Patterns
- **Dependency Injection:** Use Spring, CDI, or other DI frameworks
- **AOP:** Implement cross-cutting concerns appropriately
- **Persistence:** Follow established ORM patterns (JPA, Hibernate)
- **REST APIs:** Use JAX-RS or Spring MVC consistently

# Risk Assessment Guidelines

## Low Risk (Proceed Directly)
- Adding tests to existing test suites
- Implementing utility methods in existing classes
- Following established patterns in new classes

## Moderate Risk (Explain and Confirm)
- Modifying core business logic
- Changing public API interfaces
- Adding new dependencies
- Modifying build configuration

## High Risk (Refuse and Explain)
- Breaking backward compatibility
- Modifying critical security components
- Changes affecting multiple modules
- Operations that could break the build system