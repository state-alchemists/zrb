---
name: core-coding
description: "Activate before any coding task — reading, editing, or creating code files. Provides the mandatory Research → Strategy → Execution workflow for safe, maintainable, low-complexity code."
user-invocable: false
---
# Skill: core-coding

Activate before any coding or development task. Follow this **Research → Strategy → Execution** workflow to ensure safety, maintainability, and seamless integration.

## PHASE 1: RESEARCH & DISCOVERY

a.  **High-Level Reconnaissance:**
    - Use `LS` with limited depth for initial structure mapping.
    - Identify: source directories, test directories, configuration files, entry points, and utility/helper modules.
    - Skip listing if you already know specific file paths — use targeted `Glob` instead.

b.  **Targeted Architecture Discovery:**
    - Use `Glob` and `Grep` in parallel to map file structures, existing patterns, and available utility functions.
    - Use `Grep` with specific `regex` and `file_pattern` to minimize noise.
    - Prefer `ReadMany` over sequential `Read` calls when gathering context from related files.
    - Read dependency files (`pyproject.toml`, `package.json`, `Cargo.toml`, etc.) to confirm available libraries before using any.

## PHASE 2: STRATEGY

Before acting, reason through and state your approach explicitly:

c.  **Formulate a Grounded Plan:**
    - **Pattern Matching:** Strategy MUST match existing project guidelines and patterns exactly. New code should look as though written by the original author.
    - **Reuse Over Reinvention:** Check for existing helper or utility functions before creating new ones.
    - **Design Principles:** Apply SOLID and DRY. One reason to change per function and class.
    - **No Anticipatory Code:** Implement only what is required. Do not design for hypothetical future requirements.

d.  **Complexity Budget (non-negotiable hard limits):**

    Exceeding any limit is a design defect — restructure before continuing.

    | Metric | Limit | Remedy when exceeded |
    |--------|-------|----------------------|
    | Cyclomatic complexity | ≤ 10 per function | Extract sub-functions |
    | Cognitive complexity | ≤ 15 per function | Flatten nesting, add guard clauses |
    | Nesting depth | ≤ 2 levels | Invert conditionals; use early returns |
    | Function length | ≤ 30 lines | Extract cohesive blocks into named helpers |
    | Parameters per function | ≤ 4 | Group related params into a data object |

    **Guard clause mandate:** The happy path must never be the deepest `else`. Invert conditions to exit early:
    ```
    # Wrong — happy path buried in nesting:
    if condition:
        if other:
            do_work()

    # Right — guard clauses flatten the path:
    if not condition:
        return
    if not other:
        raise ValueError(...)
    do_work()
    ```

    **Boolean parameter prohibition:** A function that accepts a boolean to switch its internal behavior is two functions. Split it.

    **God Class/Function prohibition:** A class or function with more than one reason to change must be split. Name each extracted piece by what it does — if you cannot name it, it is not a coherent abstraction.

e.  **Testing Strategy:** Define how you will verify the change before writing any code.
    - New behavior: identify the failing test (RED) that must exist before any implementation.
    - Bug fix: identify the minimal test that reproduces the failure.
    - Refactoring: confirm existing tests pass as a baseline before touching anything.

## PHASE 3: EXECUTION (Plan → Act → Validate)

f.  **Act (Surgical Implementation):**
    - Make minimal, precise edits strictly related to the sub-task.
    - Use only existing libraries and established patterns. NEVER introduce new technical debt.
    - **Test-First for New Behavior:** Activate the `testing` skill to drive implementation with a failing test before writing production code.
    - **Transition Safety (Strangler Pattern):** When replacing a component, keep the codebase runnable at every step:
        1. Create the new component alongside the old.
        2. Update and verify all references point to the new component.
        3. Only then remove the old component — never delete before its replacement is validated.
    - **Out-of-scope structural problems:** Report them. If they block this task, activate the `refactor` skill.
    - **Code Smell Reporting:** Surface poorly structured code you encounter — report it, do not silently fix it.
    - **Documentation:** Keep documentation files in sync with code changes. Remove references to deprecated functionality.

g.  **Validate (Zero-Regression):**
    - **Validation is the only path to finality.**
    - Bug fixes: empirically reproduce the failure BEFORE applying the fix. If root cause is unclear, activate the `debug` skill.
    - After any change: run tests, linters, and type-checkers. A change is incomplete without automated verification.
    - **Test Maintenance:** If a test fails, fix it. For new tests, activate the `testing` skill.
    - If validation fails, stop and diagnose before retrying. Do not blindly repeat actions.
    - **Security check:** Code touching user input, authentication, file I/O, or sensitive data → activate the `review` skill after implementation.

h.  **Synthesis:** Journal any non-trivial discoveries per the Journaling Protocol.
