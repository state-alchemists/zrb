# PHP Guide

## Manifest & Layout

- **Manifest**: `composer.json` (deps + autoload + scripts) + `composer.lock` (commit)
- **Source**: `src/` or `app/` (Laravel); PSR-4 autoload maps namespaces to directories
- **Tests**: `tests/` at the repo root
- **PHP version**: read `composer.json` `"require"."php"` constraint — 8.1+ is current; treat 7.x as legacy

## Idioms

- **Typed properties and return types everywhere** (8.0+): `public readonly string $name;`, `function f(): User`.
- **`readonly` properties for value objects** (8.1+) and constructor property promotion: `public function __construct(public readonly string $id) {}`.
- **Enums for fixed sets** (8.1+): `enum Status: string { case Active = 'active'; case Inactive = 'inactive'; }`.
- **Strict types at the top of every file**: `declare(strict_types=1);` — prevents silent coercion.
- **Match expressions** (8.0+) over `switch` — strict comparison, returns a value, no fall-through traps.
- **Null-safe operator** (8.0+): `$user?->profile?->name`.

## Common Anti-Patterns

- **Loose comparison (`==`).** `0 == "foo"` was `true` until 8.0. Always `===` / `!==`.
- **`@` error suppression.** Hides genuine bugs. Use `try`/`catch` or explicit null checks.
- **SQL string concatenation.** Always parameterized queries — `PDO::prepare` with bound params, or framework query builders.
- **`extract($_POST)`-style request handling.** Injects variables into scope; impossible to reason about. Read named keys explicitly.
- **Catching `\Exception` or `\Throwable` and swallowing.** Catch the narrowest type; log or rethrow.
- **Static methods for non-utility logic.** Hard to test, hard to mock. Use DI containers; reach for `static` only for pure functions.

## Complexity Budget Notes

- Function length ≤30 lines: constructor with promoted properties can compress what used to be 15+ lines of boilerplate. Count the body.
- Parameters ≤4: named arguments (8.0+) make 5+ params slightly more readable but don't make them right — group into a DTO/value object.
- Nesting ≤2: PHP encourages flat code; deep nesting usually signals missing extraction.

## Tests

- **Framework**: PHPUnit (most common); Pest (a thinner DSL on top of PHPUnit, growing in popularity)
- **PHPUnit naming**: `<ClassName>Test::test<MethodUnderTest>_<scenario>`
- **Run**: `vendor/bin/phpunit --testdox --stop-on-failure`
- **Pest**: `vendor/bin/pest --stop-on-failure`
- **Don't test private methods directly.** Drive them through the public API.

## Lint, Format, Static Analysis

- **Format**: PHP-CS-Fixer (`vendor/bin/php-cs-fixer fix --dry-run`) or PHP_CodeSniffer (`vendor/bin/phpcs`)
- **Static analysis**: PHPStan (`vendor/bin/phpstan analyse` at level 6+) or Psalm (`vendor/bin/psalm`). Both find errors PHP's runtime won't.
- **Lint syntax**: `php -l <file>` — quick syntax check, but not a real linter

## Canonical Verify Sequence

```bash
composer install
vendor/bin/php-cs-fixer fix --dry-run --diff
vendor/bin/phpstan analyse
vendor/bin/phpunit --testdox
```
