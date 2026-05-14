# Refactor Methodology

**Cardinal rule: observable behavior must not change.** Refactoring is restructuring, not rewriting — distinct from adding features or fixing bugs.

## Non-Negotiable Prerequisites

**Before making any structural change, you MUST have a passing test suite.**

1. Run the existing tests with `Bash`. Confirm they pass.
2. If test coverage is insufficient for the code you intend to refactor, **stop and write characterization tests first** (see `testing.md` in this directory).
   - A characterization test captures what the code currently does so you can detect unintended changes.
   - Coverage is sufficient when all public methods and their key branches (happy path + primary error path) have at least one test each. 100% line coverage is not required, but the refactoring target must be covered.
3. Record the baseline: the exact test command and its output. This is your safety net.

**If you cannot establish a passing baseline, do not refactor.**

---

## Workflow

### PHASE 1: Understand Before Changing

1. **Read the code to be refactored thoroughly** using `ReadMany` or `Read`.
2. **Identify the code smell or structural problem** you are targeting. Be specific (name the metric or symptom).
3. **Plan atomic steps.** Each step should be small enough that a failing test immediately identifies the problematic change. Write the plan as todos using `WriteTodos`.

---

### PHASE 2: Atomic Refactoring Steps

Apply one refactoring technique at a time. After each:
- Use `Edit` (not `Write`) for surgical changes.
- Run the full test suite with `Bash`.
- If any test fails: **revert immediately** and diagnose. Do not proceed.

**Common refactoring techniques:**

| Technique | Trigger |
|-----------|---------|
| **Extract Method** | Nameable block; function too long |
| **Extract Variable** | Complex expression repeated or unreadable |
| **Inline Method** | Body is as clear as the name; indirection adds nothing |
| **Rename** | Name is ambiguous, abbreviated, or misleading |
| **Move Method/Class** | Function uses more data from another class than its own |
| **Replace Magic Number** | Literal with domain meaning → named constant |
| **Replace Conditional with Guard Clause** | Deeply nested if/else → invert and return early |
| **Replace Conditional with Polymorphism** | Type-switching if/elif chain → subclass or strategy |
| **Strangler Fig** | Large component replacement; run old and new in parallel until migration is complete |
| **Introduce Parameter Object** | Parameters that always appear together → data class/struct |

---

### PHASE 3: Verify and Integrate

1. **Run the full test suite** one final time after all planned steps.
2. **Run the linter and type-checker** (from `Makefile`, `pyproject.toml`, or `package.json`).
3. **Confirm the refactored code is genuinely simpler**, not just different.
4. **Do not introduce new behavior.** If you discovered a bug during refactoring, note it and fix it in a separate step after the refactoring is complete.

---

## Boundaries

- **Never refactor and add features simultaneously.**
- **Never refactor and fix bugs simultaneously.** Mixing changes makes failures ambiguous.
- **Stop if you lose the green test baseline.** Debug, revert, or ask for help.

---

## Output Format

1. **Code Smell Addressed**: what structural problem was fixed.
2. **Techniques Applied**: which refactoring patterns were used and where.
3. **Before/After**: key `file_path:line_number` references showing the improvement.
4. **Test Verification**: the test command and output confirming no regressions.
