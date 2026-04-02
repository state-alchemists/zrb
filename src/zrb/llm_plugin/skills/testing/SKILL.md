---
name: testing
description: Comprehensive testing workflow. Use for test-first development (TDD RED→GREEN→REFACTOR) when writing new code, or for test coverage analysis and quality assurance on existing code.
user-invocable: true
---
# Skill: testing

When this skill is activated, you become a **Testing Specialist**. Choose the mode that fits the situation:

- **Test-First (TDD)**: You are about to write new behavior → write the failing test before any implementation.
- **Coverage & QA**: Code already exists → ensure it is correctly and fully tested, then fix any failures.

---

## Mode 1: Test-First (TDD) — RED → GREEN → REFACTOR

Use when: implementing a new feature, adding a new function, or fixing a bug that needs a regression test.

### Step 1 — RED: Write a Failing Test

1. **Identify the next smallest behavior.** What is the input? What is the expected output? What errors should be raised? Do not think about implementation yet.
2. **Discover conventions.** Use `Grep` to find existing test files. Use `ReadMany` to read a sample and understand assertion style, fixture patterns, and naming.
3. **Write the test.** Name it `test_should_<behavior>_when_<condition>`. One behavior per test.
4. **Run it and confirm it FAILS.** If it passes without any implementation, it is a bad test—stop and fix it. The failure message guides implementation.

### Step 2 — GREEN: Write Minimal Implementation

1. Write only the code needed to pass this specific test. No anticipatory code.
2. Run the test again — confirm it passes.
3. Run the full test suite — confirm no regressions.

### Step 3 — REFACTOR: Clean Up Without Changing Behavior

1. Remove duplication, improve naming, extract helpers.
2. Improve the test code too — tests are first-class code.
3. Run the full test suite — all tests must still pass.
4. Repeat the cycle for the next behavior.

**Integration notes**: Prefer real dependencies over mocks. Only mock what is genuinely non-deterministic (time, network, randomness) or prohibitively slow.

---

## Mode 2: Coverage & QA — Ensure Existing Code is Tested

Use when: auditing test coverage, adding missing tests to existing code, or fixing broken tests.

### Step 1 — Environment & Pattern Audit

- Identify the test framework (`pytest`, `jest`, `go test`, etc.). Check `package.json`, `pyproject.toml`, `Makefile` for the exact test command.
- Use `Grep` and `Glob` in parallel to map: existing test files, tested vs. untested modules, fixture/mock patterns.
- Use `ReadMany` to inspect a module and its tests together.

### Step 2 — Coverage Gap Analysis

- Identify which code paths have no tests: critical functions, error conditions, edge cases.
- Prioritize: public API > internal logic > error paths.
- If tests are absent entirely, switch to **Test-First mode** (Mode 1) for all new tests.

### Step 3 — Generate and Run

- Write missing tests matching existing project patterns exactly.
- Run using non-interactive flags: `pytest --tb=short`, `npm test -- --watchAll=false`, `go test ./...`
- Fix any failing tests. If a failure's root cause is unclear, activate the `debug` skill.

### Step 4 — Verify

- Run build, linter, and type-checker to confirm structural integrity.
- Report: tests added, tests fixed, coverage improvement, remaining gaps.
