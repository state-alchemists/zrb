# Java Guide

## Manifest & Layout

- **Manifest**: `pom.xml` (Maven) or `build.gradle`/`build.gradle.kts` (Gradle). Sometimes `settings.gradle` for multi-module.
- **Source**: `src/main/java/<package>/` (Maven/Gradle convention)
- **Resources**: `src/main/resources/`
- **Tests**: `src/test/java/<package>/`
- **Java version**: read `<maven.compiler.source>` (Maven) or `sourceCompatibility`/`java.toolchain.languageVersion` (Gradle)

## Idioms

- **`final` by default.** Fields, parameters, locals — make them mutable only when you need to.
- **Records for value types** (Java 16+): `record Point(int x, int y) {}` over a class with boilerplate getters/equals/hashCode.
- **Streams for collection pipelines.** `list.stream().filter(...).map(...).toList()` — but don't force streams onto code that's clearer as a `for` loop.
- **Optional only as a return type.** Not a field type, not a parameter — that defeats the purpose.
- **Sealed types and pattern matching** (Java 17+) for closed hierarchies: `sealed interface Shape permits Circle, Square`.
- **Try-with-resources for `AutoCloseable`.** `try (var f = new FileReader(...)) { ... }` — never bare `close()` in `finally`.

## Common Anti-Patterns

- **`null` for "absent".** Use `Optional<T>` for return values; consider `@Nullable`/`@NonNull` annotations everywhere else.
- **Catching `Exception` or `Throwable`.** Catch the specific checked exception; let unchecked propagate unless you have a recovery strategy.
- **Returning mutable internal state.** `return new ArrayList<>(this.items)` over `return this.items`.
- **Premature `static` utility classes** when DI/composition would do.
- **Inheritance for code reuse.** Prefer composition; reserve inheritance for genuine "is-a" relationships.
- **Thread-unsafe singletons.** Use `enum` singleton or `LazyHolder` idiom; never naive double-checked locking.

## Complexity Budget Notes

- Function length ≤30 lines: Java's signatures + braces add baseline noise. Count the body, not the declaration lines.
- Parameters ≤4: builder pattern (or records) for things that would otherwise have 5+ params.
- Nesting ≤2: guard clauses + early return work just as well as in other languages. Don't write deeply-nested `if`/`else`.

## Tests

- **Framework**: JUnit 5 (`org.junit.jupiter`) is the default; JUnit 4 still in legacy code
- **Naming**: `methodUnderTest_givenCondition_expectedOutcome` or `should_xxx_when_yyy` — match existing files
- **Run**: `mvn test` (Maven) or `./gradlew test` (Gradle)
- **Assertions**: AssertJ (`assertThat(x).isEqualTo(y)`) is more readable than vanilla JUnit assertions
- **Mocking**: Mockito; prefer real objects when feasible

## Lint, Format

- **Format**: google-java-format or Spotless — `mvn spotless:check` / `./gradlew spotlessCheck`
- **Lint**: Checkstyle, SpotBugs, ErrorProne — check `pom.xml`/`build.gradle` for which is configured
- **Static analysis**: PMD (legacy), SonarLint (IDE), or SonarQube (CI)

## Canonical Verify Sequence

Maven:
```bash
mvn spotless:check
mvn verify              # compile + test + spotbugs/checkstyle if configured
```

Gradle:
```bash
./gradlew spotlessCheck
./gradlew check         # compile + test + lints
```
