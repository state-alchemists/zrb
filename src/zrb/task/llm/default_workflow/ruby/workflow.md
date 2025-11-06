# Ruby Development Guide

This guide provides the baseline for Ruby development. It is superseded by project-specific conventions.

## 1. Project Analysis Checklist

Before coding, inspect the project for these files to determine its conventions:

- **Dependency Management:** `Gemfile` and `Gemfile.lock`. Note the gems and their versions.
- **Ruby Version:** Look for a `.ruby-version` file.
- **Style & Linting Config:** `.rubocop.yml`. This defines the coding standard.
- **Testing Framework:** Look for a `test/` or `spec/` directory and check the `Gemfile` for dependencies like `minitest` or `rspec`.

## 2. Core Principles

- **Style:** Strictly adhere to the project's configured linter (e.g., RuboCop). If none exists, default to the Ruby Style Guide.
- **Idiomatic Ruby:** Embrace Ruby's core features:
  - Use blocks and iterators.
  - Use symbols for identifiers and strings for data.
  - Use metaprogramming responsibly.
- **Frameworks:** If the project uses a framework like Ruby on Rails, follow its conventions.

## 3. Implementation Patterns

- **Error Handling:** Replicate existing patterns for exceptions. Use `begin-rescue-end` blocks for exception handling.
- **Testing:** Use the project's existing test structure. Write unit tests for all new code.

## 4. Common Commands

- **Install Dependencies:** `bundle install`
- **Update Dependencies:** `bundle update`
- **Linting:** `bundle exec rubocop`
- **Testing:** `bundle exec rake test`, `bundle exec rspec`
