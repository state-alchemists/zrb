---
name: testing
description: Run a guided testing workflow — TDD for new behavior or coverage QA for existing code.
user-invocable: true
disable-model-invocation: true
---
# /testing

The user invoked `/testing` with: $ARGUMENTS

Procedure:

1. Ensure `core-coding` is activated for this session. If you can't recall its companion layout from earlier, re-activate via `ActivateSkill('core-coding')` — silent and auto-approved.
2. Among `core-coding`'s companion files, locate the testing methodology guide and Read it.
3. If the user has not specified a mode (TDD vs Coverage) and the request doesn't make it obvious (e.g., "add tests for foo.py" implies Coverage; "write a test for the new login flow" implies TDD), ask once before proceeding.
4. Apply the methodology to the user's request. Report in the format that guide defines.
