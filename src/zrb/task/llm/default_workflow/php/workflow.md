# PHP Development Guide

This guide provides the baseline for PHP development. It is superseded by project-specific conventions.

## 1. Project Analysis Checklist

Before coding, inspect the project for these files to determine its conventions:

- **Dependency Management:** `composer.json` and `composer.lock`. Note the dependencies and scripts.
- **PHP Version:** Look for a `.php-version` file or check `composer.json`.
- **Style & Linting Config:** `.php-cs-fixer.php`, `phpcs.xml`. These define the coding standard.
- **Testing Framework:** Look for a `tests/` directory and check `composer.json` for dependencies like `phpunit`.

## 2. Core Principles

- **Style:** Strictly adhere to the project's configured linter (e.g., PHP-CS-Fixer, PHP_CodeSniffer). If none exists, default to PSR-12.
- **Modern PHP:** Use modern PHP features, such as type declarations, strict types, and the null coalescing operator.
- **Frameworks:** If the project uses a framework like Laravel or Symfony, follow its conventions.

## 3. Implementation Patterns

- **Error Handling:** Replicate existing patterns for exceptions. Use `try-catch` blocks for exception handling.
- **Testing:** Use the project's existing test structure. Write unit tests for all new code.

## 4. Common Commands

- **Install Dependencies:** `composer install`
- **Update Dependencies:** `composer update`
- **Linting:** `vendor/bin/php-cs-fixer fix`, `vendor/bin/phpcs`
- **Testing:** `vendor/bin/phpunit`
