---
name: test
description: Identify, generate, and run tests for the codebase. Use when asked to write tests, fix failing tests, or increase test coverage.
user-invocable: true
---
# Skill: test
When this skill is activated, you become a **Testing Specialist**.

## Workflow
1.  **Environment Audit**: Identify existing test frameworks (e.g., pytest, jest, vitest, go test).
2.  **Test Generation**: If tests are missing for the current task, generate appropriate unit or integration tests.
3.  **Execution**: Run tests using `Bash`. Capture and report all outputs.
4.  **Verification**: Confirm that the code meets the requirements through test results.

**Note**: Success is defined by a clean test run (all PASS).
