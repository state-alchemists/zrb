# Debug Methodology

Find root cause before fixing. A fix without understanding the root cause creates new bugs.

**First, determine the failure type:**
- **Build/compilation failure** (type error, missing import, undefined symbol) → follow [Section A](#section-a-build-failures)
- **Behavioral failure** (wrong output, crash, test failure, unexpected behavior) → follow [Section B](#section-b-behavioral-failures)

---

## Section A: Build Failures

Use when: the compiler, type-checker, or linter is failing and you need green fast.

**Mandate**: minimum viable fix. Every extra line changed risks a new bug.

### A1 — Read the Full Error Output

Run the failing command with `Bash`. Capture complete output — later errors are often caused by earlier ones. Fix the first error first.

Common commands: `make build`, `tsc`, `mypy .`, `go build ./...`, `cargo build`, `mvn compile`

### A2 — Fix One Error at a Time

For each error (starting from the first):
1. Navigate to `file:line` with `Read`.
2. Understand context (10 lines above and below).
3. Apply the minimal fix with `Edit`. Don't refactor surrounding code.
4. Re-run the build after each fix.

**Common patterns:**
- Missing import / undefined symbol → add import or fix reference
- Type mismatch → adjust type annotation or cast
- Wrong number of arguments → align call site with signature
- Missing required field → add field with appropriate value

### A3 — Verify

Build exits with code 0. Run existing tests to confirm no behavioral regressions.

**Boundaries**: do not refactor while fixing. Don't change interfaces unless it's the only resolution — if so, update all call sites.

---

## Section B: Behavioral Failures

Use when: something runs but produces wrong results, crashes at runtime, or a test fails.

**Core mandates:**
- Reproduce first. Never diagnose from memory.
- One hypothesis at a time. Test empirically, then move to the next.

### B1 — Reproduce: Make the Failure Concrete

1. Understand the symptom: actual vs. expected behavior, exact error message, stack trace.
2. Write a minimal reproduction case — a failing test or a small script. Confirm it fails consistently.
3. If intermittent, add logging with `Edit` to capture state when it occurs.
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
5. **Add temporary instrumentation** at failure points (entry/exit, before/after suspect operations). Remove after diagnosis.

### B3 — Hypothesize and Test

List candidate root causes ranked by likelihood. Test the top hypothesis first. If refuted, eliminate and move to the next.

**Common root causes** (apply equivalent reasoning for your language/runtime):
- Off-by-one in loops or slices
- Null/None/nil not handled at a boundary
- Mutable default shared across calls (e.g., Python default argument, JS object default)
- Missing `await` on async call (result is a promise/coroutine, not a value)
- Identity vs. equality confusion (`is`/`===` vs `==`)
- State leaking between test cases (shared global or fixture not reset)
- Encoding mismatch (bytes vs str, UTF-8 vs Latin-1)
- Race condition on shared mutable state
- Ownership/lifetime error (use-after-free, moved value — Rust/C++)
- Implicit type coercion producing unexpected values (JS `==`, SQL implicit casts)

### B4 — Fix and Verify

1. Apply the minimal fix with `Edit`. Change only what caused the bug.
2. Run the reproduction case — must now pass.
3. Run the full test suite — no new failures.
4. Remove any temporary instrumentation added in B2.
5. If the fix is non-obvious, add a short comment explaining the "why."

---

## Output Format

1. **Failure type**: build failure or behavioral failure.
2. **Root cause**: one precise sentence — what, where, and why.
3. **Evidence**: reproduction case output before and after.
4. **Fix**: `file_path:line_number` — what changed.
5. **Verification**: test/build output confirming green.
