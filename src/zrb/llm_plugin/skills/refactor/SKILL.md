---
name: refactor
description: Safe structural refactoring that preserves existing behavior. Establishes test coverage first, then makes small atomic changes with verification at each step. Use when improving code structure, reducing complexity, or removing duplication in working code.
user-invocable: true
---
# Skill: refactor

When this skill is activated, you enter **Refactoring Mode**. The cardinal rule: **the observable behavior of the code must not change.** Refactoring is restructuring, not rewriting. It is distinct from adding features or fixing bugs.

## Non-Negotiable Prerequisites

**Before making any structural change, you MUST have a passing test suite.**

1. Run the existing tests with `Bash`. Confirm they pass.
2. If test coverage is insufficient for the code you intend to refactor, **stop and write characterization tests first** (use the `tdd` skill).
   - A characterization test captures what the code currently does—even if that behavior is wrong—so you can detect unintended changes.
3. Record the baseline: the exact test command and its output. This is your safety net.

**If you cannot establish a passing baseline, do not refactor.**

---

## Workflow

### PHASE 1: Understand Before Changing

1. **Read the code to be refactored thoroughly** using `ReadMany` or `Read`.
2. **Identify the code smell or structural problem** you are targeting. Be specific:
   - "This function is 150 lines and does three unrelated things."
   - "This logic is copy-pasted in 4 places with minor variations."
   - "Cyclomatic complexity is >15 due to deeply nested conditionals."
3. **Plan atomic steps.** Each step should be small enough that a failing test immediately identifies the problematic change. Write the plan in a `<thinking>` block or as todos using `WriteTodos`.

---

### PHASE 2: Atomic Refactoring Steps

Apply one refactoring technique at a time. After each:
- Use `Edit` (not `Write`) for surgical changes.
- Run the full test suite with `Bash`.
- If any test fails: **revert immediately** and diagnose. Do not proceed.

**Common refactoring techniques:**

| Technique | When to Apply |
|-----------|---------------|
| **Extract Method** | A block of code can be named and reused; function is too long |
| **Extract Variable** | A complex expression appears more than once or is hard to read |
| **Inline Method** | A method's body is as clear as its name; indirection adds no value |
| **Rename** | A name is ambiguous, abbreviated, or misleading |
| **Move Method/Class** | A function uses more data from another class than its own |
| **Replace Magic Number** | A literal value has domain meaning (use a named constant) |
| **Replace Conditional with Guard Clause** | Deeply nested `if/else`; invert condition to return/raise early |
| **Replace Conditional with Polymorphism** | `if/elif` chains switching on type; use subclassing or strategy pattern |
| **Strangler Fig** | Replacing a large component; build new alongside old, migrate callers, remove old |
| **Introduce Parameter Object** | A group of parameters always appear together; group into a dataclass/struct |

---

### PHASE 3: Verify and Integrate

1. **Run the full test suite** one final time after all planned steps.
2. **Run the linter and type-checker** (from `Makefile`, `pyproject.toml`, or `package.json`).
3. **Read the refactored code** with `Read` and confirm it is genuinely simpler, not just different.
4. **Do not introduce new behavior.** If you discovered a bug during refactoring, note it and fix it in a separate step after the refactoring is complete.

---

## Boundaries

- **Never refactor and add features simultaneously.** These are separate commits.
- **Never refactor and fix bugs simultaneously.** Mixing changes makes failures ambiguous.
- **Stop if you lose the green test baseline.** Debug, revert, or ask for help.

---

## Output Format

1. **Code Smell Addressed**: What structural problem was fixed.
2. **Techniques Applied**: Which refactoring patterns were used and where.
3. **Before/After**: Key `file_path:line_number` references showing the improvement.
4. **Test Verification**: The test command and output confirming no regressions.
