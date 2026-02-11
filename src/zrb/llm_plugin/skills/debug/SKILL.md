---
name: debug
description: Systematically troubleshoot and resolve complex bugs. Use when an issue is difficult to reproduce or has unknown root causes.
user-invocable: true
---
# Skill: debug
When this skill is activated, you switch into **Detective Mode**. You follow a structured scientific process to isolate and fix the root cause of an issue.

## Workflow
1.  **Reproduction (Observation)**:
    - Capture the exact error message and context.
    - Create a minimal, automated reproduction script or test case.
2.  **Evidence Gathering (Investigation)**:
    - Use `Read` and `Grep` to trace data flow through the suspect system.
    - Use `Bash` to inspect system state, logs, or process memory.
    - Use `AnalyzeFile` for deep logic understanding of complex modules.
3.  **Hypothesis Formation**:
    - Based on evidence, list potential root causes.
    - Prioritize them by likelihood and ease of verification.
4.  **Isolation (Testing)**:
    - Use `Edit` to add targeted logging or temporary state assertions.
    - Run the reproduction case to confirm or refute each hypothesis.
5.  **Solution & Verification**:
    - Propose a targeted fix.
    - Apply the fix and confirm the reproduction case now passes.
    - Run the full test suite to ensure no regressions.

## Debugging Checklist
- [ ] Reproducible?
- [ ] Root cause identified?
- [ ] Fix verified?
- [ ] Regression testing passed?

**Note**: Focus on identifying the *why* before applying the *how*.
