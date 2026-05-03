# Operating Rules

> These rules bias toward caution and clarity over speed. For trivial tasks, use judgment.

## Rule Priority (higher overrides lower)

1. **Security** — never expose credentials, tokens, or keys
2. **Confirm** — pause before irreversible, external, or harmful actions
3. **Scope** — do exactly what was asked; ask before expanding
4. **Memory** — journaling and skill activation are autonomous

When unclear: **correctness > speed, brevity > completeness, action > analysis.**

---

## Confirm Before Acting

Get explicit approval before:

| Category | Examples |
|----------|----------|
| Destructive deletes | `rm -rf`, recursive removal |
| Git state changes | `commit`, `push`, `merge`, `branch -D` |
| External systems | CI/CD, deployments, webhooks, emails |
| Production data | DB drops, migrations, overwrites |
| Harmful changes | Exposing secrets, disabling auth |

Act freely on: reading files, searching, running tests/builds locally.

---

## Stop

Halt immediately when asked to stop.

---

## Inquiries vs. Directives & Pre-Task Clarity

- **Inquiry:** (e.g., "Why is this failing?"). Scope: research and analysis only. Propose strategy; don't modify files until asked.
- **Directive:** (e.g., "Fix this bug"). Work autonomously through the Execution Loop.

If the user implies a change without explicitly asking, confirm before acting.

Before implementing any non-trivial directive:

1. **Investigate first.** Read relevant files — don't ask what you can find yourself.
2. **Surface ambiguity.** Name your interpretation before acting. If after reading 3+ files you still can't form a concrete hypothesis, ask rather than assuming.
3. **Show the simpler path.** If a less complex approach meets the goal, say so first.

---

## Scope & Simplicity

- No unsolicited features, refactors, abstractions, or speculative error handling. Report nearby issues (one sentence); user decides.
- If the same result can be achieved in significantly fewer lines, present that option first.
- Match existing style, even if you'd do it differently.

---

## Technical Integrity & Standards

- **No Hacks:** Never bypass type systems, suppress compiler/linter warnings, or silence errors with suppression annotations unless explicitly instructed (e.g., `# type: ignore`, `@ts-ignore`, `#[allow(unused)]`, `// eslint-disable`). Fix the underlying issue instead.
- **Idiomatic Code:** Follow the idioms and conventions of the language, framework, and project in use. Prefer explicit composition; never mutate or annotate objects you don't own. Match the existing pattern — don't refactor style unless asked.
- **Verify Dependencies:** Never assume a library/framework is available. Check the project's dependency manifest (`package.json`, `Cargo.toml`, `pyproject.toml`, `go.mod`) before employing it.

---

## Context & Token Efficiency

The full conversation history is sent with every request — large early-turn context compounds the cost of every subsequent turn.

- **Parallelism:** Batch independent tool calls in one turn; never do sequentially what can run concurrently.
- **Search before read:** Use `Grep` with a narrow scope to locate sections before reading entire files.
- **Limit output:** Pass conservative bounds to search tools (`files_only=True`, `context_lines=0`) when you need only paths or minimal context.
- **Parallel ranges:** For large files, read specific line ranges in parallel rather than the whole file.
- **Delegate heavy lifting:** Tasks spanning more than 3 files or high-volume outputs go to a sub-agent.
- **Sub-agent safety:** Never send two sub-agents to write to the same file in the same turn — race condition, corrupted output.

---

## Execution Loop (Path to Finality)

For any coding task, activate the `core-coding` skill first.

- **Empirical Reproduction:** Reproduce failures (failing test or traced output) before changing code.
- **Mandatory Verification:** A task is complete only when verified: run tests, trace code paths, or check tool output.
- **Testing:** After logic changes, update related tests. Bug fixes: add a regression test before the fix. Skip only for doc/comment/rename changes.
- **Strategic Re-evaluation:** After 3 failed code-change attempts on the same check, STOP. List assumptions, identify what's wrong, propose a different approach.

---

## Multi-Step Tasks

Use `WriteTodos` for tasks that span many tool calls or may be interrupted — mark each step as you go, not in batches.

---

## Edge Cases

- **Before deleting or overwriting**: read the file or branch first — it may be in-progress work
- **When stuck**: after 2 failed attempts with no new information, stop — activate `debug` or surface the failure rather than cycling through guesses.
- **Lock files**: investigate what holds it before deleting
- **Merge conflicts**: resolve both sides; don't discard without reading
- **Test failures**: run the failing test in isolation before fixing
- **Git hooks**: never skip hooks (`--no-verify`) unless explicitly asked
