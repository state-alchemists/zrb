---
name: core-coding
description: "Activate when the turn changes source, test, or config files. Provides the Research → Strategy → Execution workflow, the complexity budget, and deep-dive companions (testing, debug, observability, refactor, review)."
user-invocable: false
---
# Skill: core-coding

Follow **Research → Strategy → Execution** for every coding task.

## Deep-Dive Companions

When the current step matches a trigger below, `Read` the named companion from this skill's directory (the activation header lists the directory path and all companion paths). Companions are not pre-loaded — pull them on demand.

| Trigger | Companion |
|---------|-----------|
| About to write, modify, or audit a test | `workflows/testing.md` |
| Something is broken locally (build error, failing test, wrong output) and root cause is unclear | `workflows/debug.md` |
| A **running or deployed** system is failing and you can't reproduce it locally — crash/core dump, memory/heap dump, OOM, or diagnosis via `kubectl` / Grafana / Prometheus / Elasticsearch | `workflows/observability.md` (helper scripts in `tools/`) |
| Code structure needs improvement (complexity, duplication) | `workflows/refactor.md` |
| Reviewing changes for correctness, security, or quality | `workflows/review.md` |
| Code touches user input, auth, file I/O, or sensitive data | `workflows/review.md` (security audit checklist) |
| First substantial edit in a project — identify the language from the manifest | `languages/<lang>.md` (one of `python`, `typescript`, `go`, `rust`, `java`, `ruby`, `php`) |

Everything in this skill and its companions is a **default**: explicit user instructions and project guidelines (CLAUDE.md, AGENTS.md, custom skills, project files) override it wherever they conflict. Core guidance fills in the gaps.

## PHASE 1: RESEARCH & DISCOVERY

Follow the **Scientific Method**: form a hypothesis → test it → analyze results. Avoid random changes.

### a.  **High-Level Reconnaissance:**

- Use `LS` with limited depth for initial structure mapping.
- Identify: source directories, test directories, config files, entry points, and utility modules.
- Skip if you already know specific file paths — use targeted `Glob` instead.

### b.  **Targeted Architecture Discovery:**

- Use `Glob` and `Grep` in parallel to map file structures, existing patterns, and utility functions.
- Use `Grep` with specific `regex` and `file_pattern` to minimize noise.
- Issue several `Read` calls in parallel when gathering context from related files.
- **Before modifying any existing function, method, or class signature:** use `LspFindReferences` if LSP is available, otherwise `Grep`. Find all call sites and include updating them in your plan.
- **Before moving or removing any file or directory:** use `Grep` to find all imports and path references first.

## PHASE 2: STRATEGY

### c.  **Formulate a Grounded Plan:**

- **Language & Framework Idioms:** identify the language, framework, and version from dependency files and existing code. Apply idiomatic conventions — a pattern correct in one language may be an anti-pattern in another. Never add attributes or behavior to objects owned by a library; wrap them in a type you own.
- **Pattern Matching:** strategy MUST match existing project guidelines and patterns exactly. New code should look as though written by the original author.
- **Reuse existing helpers** before creating new ones.
- **Apply SOLID and DRY.** One reason to change per function and class.
- **No magic numbers, strings, or unexplained constants.** Name every value that carries meaning.

### d.  **Complexity Budget (default hard limits):**

Exceeding a limit is a design defect — restructure before continuing. Project guidelines override these **limits and their enforcement**: a project may set different numbers, or state that a number is a target for new code rather than an invariant. Where it does, follow the project and do not cite the number as if it were enforced.

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
- **Re-read before you Edit.** Apply every `Edit` against a `Read`'s output you can see in this conversation, never against memory: if you read the file earlier, or edited it since, `Read` the target region again and copy `old_text` from the fresh output. A stale block fails to match or edits the wrong region, and each miss costs more than the re-read did.
- Keep functions within the Complexity Budget. Place helpers below callers.
- **Strangler Pattern:** when replacing a component, keep codebase runnable at every step: new alongside old → update references → remove old.
- **Out-of-scope structural problems:** report them. If they block this task, Read `workflows/refactor.md` and address atomically.
- **Code Smell Reporting:** report poorly structured code you encounter — don't silently fix it.
- **Docs:** keep documentation in sync; remove deprecated references.

### g.  **Validate (Zero-Regression):**

- Validation is the only path to finality. A change is done when a focused test, lint, or type check has run and passed — not when the edit lands. If the project has no such check, name what you looked for.
- Bug fixes: reproduce before fixing. A fix you cannot demonstrate reverses a symptom you never confirmed. If root cause is unclear, Read `workflows/debug.md`.
- After any change: run tests, linters, and type-checkers. Run the focused test first; a full suite that takes minutes is not a reason to skip the one that takes seconds.
- **Removals get proved, not assumed.** When the task was to eliminate something, `Grep` the changed files for the literal you removed and require zero hits — `password123` for a credential moved to config, `legacy_auth(` for a migrated call, `console.log` for a stripped debug print, the old module path for a dropped import. Tests pass on code that still carries the string you were asked to delete, which is why this is a separate step and not a consequence of a green suite.
- **Touched credentials, auth, user input, or file I/O?** Read `workflows/review.md` and run its security checklist before declaring done — don't wait for a review request.
- If validation fails, diagnose before retrying.

### h.  **Synthesis:**

For user-facing output (docs, error messages, commit messages), apply writing quality standards from `core-writing`.
