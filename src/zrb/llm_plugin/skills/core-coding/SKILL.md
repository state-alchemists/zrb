---
name: core-coding
description: "Activate before any coding task — reading, editing, or creating code files. Provides the mandatory Research → Strategy → Execution workflow plus the complexity budget and specialised deep-dive companions (testing, debug, refactor, review)."
user-invocable: false
---
# Skill: core-coding

Follow **Research → Strategy → Execution** for every coding task.

## Deep-Dive Companions

When the current step matches a trigger below, `Read` the named companion from this skill's directory (the activation header lists the directory path and all companion paths). Companions are not pre-loaded — pull them on demand.

| Trigger | Companion |
|---------|-----------|
| About to write, modify, or audit a test | `workflows/testing.md` |
| Something is broken and root cause is unclear | `workflows/debug.md` |
| Code structure needs improvement (complexity, duplication) | `workflows/refactor.md` |
| Reviewing changes for correctness, security, or quality | `workflows/review.md` |
| Code touches user input, auth, file I/O, or sensitive data | `workflows/review.md` (security audit checklist) |
| First substantial edit in a project — identify the language from the manifest | `languages/<lang>.md` (one of `python`, `typescript`, `go`, `rust`, `java`, `ruby`, `php`) |

If the user has provided custom guidelines for any of the above (in CLAUDE.md, AGENTS.md, their own skills, or project files), prefer those over the core companion. Core companions fill in the gaps.

## PHASE 1: RESEARCH & DISCOVERY

Follow the **Scientific Method**: form a hypothesis → test it → analyze results. Avoid random changes.

### a.  **High-Level Reconnaissance:**

- Use `LS` with limited depth for initial structure mapping.
- Identify: source directories, test directories, config files, entry points, and utility modules.
- Skip if you already know specific file paths — use targeted `Glob` instead.

### b.  **Targeted Architecture Discovery:**

- Use `Glob` and `Grep` in parallel to map file structures, existing patterns, and utility functions.
- Use `Grep` with specific `regex` and `file_pattern` to minimize noise.
- Prefer `ReadMany` over sequential `Read` when gathering context from related files.
- **Before modifying any existing function, method, or class signature:** use `LspFindReferences` if LSP is available, otherwise `Grep`. Find all call sites and include updating them in your plan.
- **Before moving or removing any file or directory:** use `Grep` to find all imports and path references first.

## PHASE 2: STRATEGY

### c.  **Formulate a Grounded Plan:**

- **Language & Framework Idioms:** identify the language, framework, and version from dependency files and existing code. Apply idiomatic conventions — a pattern correct in one language may be an anti-pattern in another. Never add attributes or behavior to objects owned by a library; wrap them in a type you own.
- **Pattern Matching:** strategy MUST match existing project guidelines and patterns exactly. New code should look as though written by the original author.
- **Reuse existing helpers** before creating new ones.
- **Apply SOLID and DRY.** One reason to change per function and class.
- **No magic numbers, strings, or unexplained constants.** Name every value that carries meaning.

### d.  **Complexity Budget (non-negotiable hard limits):**

Exceeding any limit is a design defect — restructure before continuing.

| Metric | Limit | Remedy when exceeded |
|--------|-------|----------------------|
| Cyclomatic complexity | ≤ 10 per function | Extract sub-functions |
| Cognitive complexity | ≤ 15 per function | Flatten nesting, add guard clauses |
| Nesting depth | ≤ 2 levels | Invert conditionals; use early returns |
| Function length | ≤ 30 lines | Extract cohesive blocks into named helpers |
| Parameters per function | ≤ 4 | Group related params into a data object |

**Guard clause mandate:** invert conditions to exit early; the happy path must never be the deepest `else`.

**Boolean parameter prohibition:** a boolean parameter = two functions. Split them.

**God Class/Function prohibition:** one reason to change per class/function. If you can't name the extracted piece, it's not a coherent abstraction.

### e.  **Testing Strategy:** define verification before writing code. For test-first methodology, Read `workflows/testing.md`.

- New behavior: identify the failing test (RED) first.
- Bug fix: identify the minimal reproduction test first.
- Refactoring: confirm existing tests pass as baseline before touching anything.

## PHASE 3: EXECUTION (Plan → Act → Validate)

### f.  **Act (Surgical Implementation):**

- Minimal, precise edits only. One logical change per task (atomic). Use existing libraries and patterns.
- Keep functions focused (~30-50 lines). Place helpers below callers.
- **Strangler Pattern:** when replacing a component, keep codebase runnable at every step: new alongside old → update references → remove old.
- **Out-of-scope structural problems:** report them. If they block this task, Read `workflows/refactor.md` and address atomically.
- **Code Smell Reporting:** report poorly structured code you encounter — don't silently fix it.
- **Docs:** keep documentation in sync; remove deprecated references.

### g.  **Validate (Zero-Regression):**

- Validation is the only path to finality.
- Bug fixes: reproduce before fixing. If root cause is unclear, Read `workflows/debug.md`.
- After any change: run tests, linters, and type-checkers.
- If validation fails, diagnose before retrying.

### h.  **Synthesis:**

journal non-trivial discoveries per the Journaling Protocol. For user-facing output (docs, error messages, commit messages), apply writing quality standards from `core-writing`.
