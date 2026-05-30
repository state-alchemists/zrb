---
name: review
description: Rigorous code review covering correctness, security (OWASP Top 10), and quality.
user-invocable: true
disable-model-invocation: true
---
# /review

The user invoked `/review` with: $ARGUMENTS

Procedure:

1. Ensure `core-coding` is activated for this session. If you can't recall its companion layout from earlier, re-activate via `ActivateSkill('core-coding')` — silent and auto-approved.
2. Among `core-coding`'s companion files, locate the review methodology guide and Read it.
3. Identify scope from the user's input. If unspecified, default to `git diff HEAD` against changed files in the current working tree.
4. **For large diffs** (>10 changed files or >500 changed lines), delegate to the `code-reviewer` agent per the instruction in the review guide rather than reviewing inline.
5. Do not modify code during review — produce findings only.
6. Report in the format that guide defines (summary, strengths, findings with severity + `file_path:line`, verdict).
