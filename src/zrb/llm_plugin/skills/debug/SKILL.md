---
name: debug
description: Systematically troubleshoot and resolve complex bugs. Use when an issue is difficult to reproduce or has unknown root causes.
user-invocable: true
---
# Skill: debug
When this skill is activated, you switch into **Detective Mode**. You follow a structured, scientific, and empirically-driven process to isolate and fix the root cause of an issue.

## Core Mandates
- **Empirical Reproduction First:** You MUST empirically reproduce the failure (with a new test case, reproduction script, or exact command execution) BEFORE applying any fix.
- **Context Efficiency:** Use search tools extensively to understand data flows. Limit output sizes and combine turns to avoid context window exhaustion.

## Workflow
1.  **Reproduction (Observation)**:
    - Capture the exact error message, stack trace, and context.
    - Create a minimal, automated reproduction script or test case that reliably fails.
2.  **Evidence Gathering (Investigation)**:
    - **Systematically map the codebase:** Use `Grep` and `Glob` in parallel to trace data flow through the suspect system. Limit scopes with specific regex and include/exclude patterns.
    - Inspect system state, logs, or process memory. Read small files entirely or read specific ranges of large files to minimize context overhead.
    - Only use deep logic analysis (`AnalyzeFile`/`AnalyzeCode`) if `Read` and `Grep` are insufficient.
3.  **Hypothesis Formation (Strategy)**:
    - Based on empirical evidence, formulate a grounded hypothesis in a `<thinking>` block.
    - Prioritize root causes by likelihood and ease of verification.
4.  **Isolation (Testing)**:
    - Add targeted logging or temporary state assertions.
    - Run the reproduction case to confirm or refute each hypothesis.
5.  **Solution & Verification (Execution)**:
    - Propose a targeted, surgical fix. Match existing patterns exactly. Do not refactor unrelated code.
    - Apply the fix and confirm the reproduction case now passes.
    - Run the full project-specific test suite, linters, and type-checkers to ensure no regressions were introduced.
    - Provide a high-signal, concise report of the root cause and the applied fix without conversational filler.

## Debugging Checklist
- [ ] Empirically reproducible?
- [ ] Root cause identified via tracing?
- [ ] Surgical fix applied matching existing patterns?
- [ ] Reproduction case now passing?
- [ ] Full regression testing (builds, linters, tests) passed?