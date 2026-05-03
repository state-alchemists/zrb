---
name: core-coding
description: "Activate before any coding task — reading, editing, or creating code files. Provides the mandatory Research → Strategy → Execution workflow for safe, maintainable, low-complexity code."
user-invocable: false
---
# Skill: core-coding

Follow **Research → Strategy → Execution** for every coding task.

## Supplementary Skill Gates

Activate at the moment the trigger applies — do not defer:

| Trigger | Activate |
|---------|---------|
| About to write or modify a test | `testing` |
| Something is broken and root cause is unclear | `debug` |
| Code structure needs improvement (complexity, duplication) | `refactor` |
| Code touches user input, auth, file I/O, or sensitive data | `review` |

## PHASE 1: RESEARCH & DISCOVERY

a.  **High-Level Reconnaissance:**
    - Use `LS` with limited depth for initial structure mapping.
    - Identify: source directories, test directories, config files, entry points, and utility modules.
    - Skip if you already know specific file paths — use targeted `Glob` instead.

b.  **Targeted Architecture Discovery:**
    - Use `Glob` and `Grep` in parallel to map file structures, existing patterns, and utility functions.
    - Use `Grep` with specific `regex` and `file_pattern` to minimize noise.
    - Prefer `ReadMany` over sequential `Read` when gathering context from related files.
    - Read dependency files (`pyproject.toml`, `package.json`, `Cargo.toml`, etc.) before using any library.
    - **Before modifying any existing function, method, or class signature:** use `LspFindReferences` if LSP is available, otherwise `Grep`. Find all call sites and include updating them in your plan.
    - **Before moving or removing any file or directory:** use `Grep` to find all imports and path references first.

## PHASE 2: STRATEGY

c.  **Formulate a Grounded Plan:**
    - **Language & Framework Idioms:** Identify the language, framework, and version from dependency files and existing code. Apply idiomatic conventions — a pattern correct in one language may be an anti-pattern in another. Never add attributes or behavior to objects owned by a library; wrap them in a type you own.
    - **Pattern Matching:** Strategy MUST match existing project guidelines and patterns exactly. New code should look as though written by the original author.
    - **Reuse existing helpers** before creating new ones.
    - **Apply SOLID and DRY.** One reason to change per function and class.
    - **No Anticipatory Code:** Implement only what is required.

d.  **Complexity Budget (non-negotiable hard limits):**

    Exceeding any limit is a design defect — restructure before continuing.

    | Metric | Limit | Remedy when exceeded |
    |--------|-------|----------------------|
    | Cyclomatic complexity | ≤ 10 per function | Extract sub-functions |
    | Cognitive complexity | ≤ 15 per function | Flatten nesting, add guard clauses |
    | Nesting depth | ≤ 2 levels | Invert conditionals; use early returns |
    | Function length | ≤ 30 lines | Extract cohesive blocks into named helpers |
    | Parameters per function | ≤ 4 | Group related params into a data object |

    **Guard clause mandate:** Invert conditions to exit early; the happy path must never be the deepest `else`.

    **Boolean parameter prohibition:** A boolean parameter = two functions. Split them.

    **God Class/Function prohibition:** One reason to change per class/function. If you can't name the extracted piece, it's not a coherent abstraction.

e.  **Testing Strategy:** Define verification before writing code.
    - New behavior: identify the failing test (RED) first.
    - Bug fix: identify the minimal reproduction test first.
    - Refactoring: confirm existing tests pass as baseline before touching anything.

## PHASE 3: EXECUTION (Plan → Act → Validate)

f.  **Act (Surgical Implementation):**
    - Minimal, precise edits only. Use existing libraries and patterns.
    - **Test-First for New Behavior:** Activate `testing` skill before writing production code.
    - **Strangler Pattern:** When replacing a component, keep codebase runnable at every step: new alongside old → update references → remove old.
    - **Out-of-scope structural problems:** Report them. If they block this task, activate `refactor`.
    - **Code Smell Reporting:** Report poorly structured code you encounter — don't silently fix it.
    - **Docs:** Keep documentation in sync; remove deprecated references.

g.  **Validate (Zero-Regression):**
    - Validation is the only path to finality.
    - Bug fixes: reproduce before fixing. If root cause is unclear, activate `debug`.
    - After any change: run tests, linters, and type-checkers.
    - If validation fails, diagnose before retrying.

h.  **Synthesis:** Journal non-trivial discoveries per the Journaling Protocol.
