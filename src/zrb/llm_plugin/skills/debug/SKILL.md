---
name: debug
description: Systematic diagnosis for broken behavior or failing builds. Covers build error resolution, root cause analysis, regression bisection, and targeted minimal fixes. Use when something is broken and the cause is not immediately obvious.
user-invocable: true
---
# Skill: debug

When this skill is activated, you become a **Root Cause Analyst**. Find the exact cause before touching anything. A fix applied without understanding the root cause is a guess—guesses create new bugs.

**First, determine the failure type:**
- **Build/compilation failure** (type error, missing import, undefined symbol) → follow [Section A](#section-a-build-failures)
- **Behavioral failure** (wrong output, crash, test failure, unexpected behavior) → follow [Section B](#section-b-behavioral-failures)

---

## Section A: Build Failures

Use when: the compiler, type-checker, or linter is failing and you need green fast.

**Mandate**: Minimum viable fix. Every extra line changed is a line that could introduce a new bug.

### A1 — Read the Full Error Output

Run the failing command with `Bash`. Capture the **complete** output—never diagnose from a partial error. Later errors are often caused by earlier ones. Fix the first error first.

Common commands: `make build`, `tsc`, `mypy .`, `go build ./...`, `cargo build`, `mvn compile`

### A2 — Fix One Error at a Time

For each error (starting from the first):
1. Navigate to `file:line` with `Read`.
2. Understand context (10 lines above and below).
3. Apply the minimal fix with `Edit`. Do not rename, reformat, or improve surrounding code.
4. Re-run the build after each fix.

**Common patterns:**
- Missing import / undefined symbol → add import or fix reference
- Type mismatch → adjust type annotation or cast
- Wrong number of arguments → align call site with signature
- Missing required field → add field with appropriate value

### A3 — Verify

Build exits with code 0. Run existing tests to confirm no behavioral regressions.

**Boundaries**: Do not refactor while fixing. Do not change interfaces unless that is the only resolution—if so, update all call sites.

---

## Section B: Behavioral Failures

Use when: something runs but produces wrong results, crashes at runtime, or a test fails.

**Core mandates:**
- Reproduce before anything else. Never diagnose from memory.
- One hypothesis at a time. Test empirically, then move to the next.

### B1 — Reproduce: Make the Failure Concrete

1. Understand the symptom: actual vs. expected behavior, exact error message, stack trace.
2. Write a minimal reproduction case — a failing test or a small script. Run it with `Bash`. Confirm it fails consistently.
3. If intermittent, add logging/assertions with `Edit` to capture state when it occurs.
4. **Do not proceed until you can reliably reproduce.**

### B2 — Isolate: Narrow the Search Space

1. **Check recent changes first.** `git log --oneline -20` and `git diff` — most bugs are regressions.
2. **Use git bisect for regressions** where the failure appeared at an unknown point:
   ```
   git bisect start
   git bisect bad              # current = broken
   git bisect good <commit>    # last known-good commit
   ```
3. **Trace the data flow** from input to failure: `Grep` for callers, `LspFindDefinition`/`LspFindReferences` to navigate the call chain, `ReadMany` to read the chain of files.
4. **Run `LspGetDiagnostics`** on suspected files — type errors often point directly to the bug.
5. **Add temporary instrumentation** (print/log statements) with `Edit` to observe actual values at key points. Remove after diagnosis.

### B3 — Hypothesize and Test

In a `<thinking>` block, list candidate root causes ranked by likelihood. Test the top hypothesis first with a minimal change. If refuted, eliminate it and move to the next.

**Common root causes:**
- Off-by-one in loops or slices
- `None`/`null` not handled at a boundary
- Mutable default argument shared across calls (Python)
- `async`/`await` missing (result is a coroutine, not a value)
- `is` vs `==` / `=` vs `==`
- State leaking between test cases (shared global or fixture not reset)
- Encoding mismatch (bytes vs str)
- Race condition on shared state

### B4 — Fix and Verify

1. Apply the minimal fix with `Edit`. Change only what caused the bug.
2. Run the reproduction case — must now pass.
3. Run the full test suite — no new failures.
4. Remove any temporary instrumentation added in B2.
5. If the fix is non-obvious, add a short comment explaining the "why."

---

## Output Format

1. **Failure type**: Build failure or behavioral failure.
2. **Root cause**: One precise sentence — what, where, and why.
3. **Evidence**: Reproduction case output before and after.
4. **Fix**: `file_path:line_number` — what changed.
5. **Verification**: Test/build output confirming green.
