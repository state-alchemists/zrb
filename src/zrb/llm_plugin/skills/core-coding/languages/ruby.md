# Ruby Guide

## Manifest & Layout

- **Manifest**: `Gemfile` (deps) + `Gemfile.lock` (locked versions, commit). `<project>.gemspec` for libraries published as gems.
- **Source**: `lib/<project>/` for libraries; `app/` for Rails projects
- **Tests**: `spec/` (RSpec convention) or `test/` (Minitest convention) — match what's there
- **Ruby version**: read `.ruby-version` file or the `ruby` directive in `Gemfile`

## Idioms

- **Blocks for iteration and resource management.** `each`, `map`, `select`, `reduce`; `File.open(path) do |f| ... end` for auto-close.
- **Method names ending in `?` for predicates, `!` for destructive variants.** `empty?`, `gsub!`.
- **Hash literal shorthand for keyword args** (3.1+): `{ id:, name: }` when the local variable matches the key.
- **Pattern matching** (3.0+) for structural destructuring: `case h in { id:, name: String => name }`.
- **Lazy evaluation with `||=`.** `@cache ||= compute_expensive_thing`.
- **Heredocs for multi-line strings.** `<<~SQL ... SQL` (the `~` strips leading indentation).

## Common Anti-Patterns

- **Monkey-patching core classes.** `String#my_helper` pollutes everyone's code. Use a module + refinement, or put the helper on your own class.
- **`nil` ambiguity.** Doesn't distinguish "absent" from "false-but-present" cleanly. Be deliberate; consider `Maybe`/sentinel objects in critical paths.
- **String interpolation in SQL.** `"WHERE id = #{params[:id]}"` is injection. Always parameterize: `where(id: params[:id])`.
- **Rescuing `Exception`.** Catches `SignalException`, `SystemExit`, `Interrupt`. Catch `StandardError` (the default for bare `rescue`) — or a specific subclass.
- **Cleverness over clarity.** Ruby's expressiveness invites one-liners that nobody can read in three months. Optimize for the reader.
- **N+1 queries in Rails.** Always `.includes(:assoc)` when iterating; use `bullet` gem in dev to catch them.

## Complexity Budget Notes

- Function length ≤30 lines: Ruby methods often end up short because of blocks and `Enumerable`. If a method is over 30 lines, blocks are usually the way to split it.
- Parameters ≤4: keyword arguments (`def f(id:, name:, age:)`) are preferred over positional for 3+ params even before the limit kicks in.
- Nesting ≤2: prefer guard clauses (`return unless x`) and early returns.

## Tests

- **Framework**: RSpec (most common) or Minitest (stdlib)
- **RSpec naming**: `describe ClassName do … it "behavior" do … end end`
- **Run RSpec**: `bundle exec rspec --fail-fast --format documentation`
- **Run Minitest**: `bundle exec rake test` or `ruby -Itest test/foo_test.rb`
- **Avoid mocks for value objects.** Mock the boundaries (network, DB, time); use real objects elsewhere.

## Lint, Format

- **Lint + format**: RuboCop — `bundle exec rubocop` (check) / `bundle exec rubocop -A` (autocorrect). Config in `.rubocop.yml`.
- **Type checking** (optional, gaining adoption): Sorbet (`srb tc`) or RBS + Steep (`bundle exec steep check`)

## Canonical Verify Sequence

```bash
bundle install
bundle exec rubocop
bundle exec rspec        # or: bundle exec rake test
```
