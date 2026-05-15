---
name: refactor
description: Safe structural refactoring that preserves observable behavior — establishes a test baseline, applies atomic changes, verifies at each step.
user-invocable: true
disable-model-invocation: true
---
# /refactor

The user invoked `/refactor` with: $ARGUMENTS

Procedure:

1. Ensure `core-coding` is activated for this session. If you can't recall its companion layout from earlier, re-activate via `ActivateSkill('core-coding')` — silent and auto-approved.
2. Among `core-coding`'s companion files, locate the refactor methodology guide and Read it.
3. **Before any structural change**, establish a passing test baseline as the guide requires. If coverage is insufficient, surface this to the user and offer to write characterization tests first (using the testing guide in the same companion set).
4. Apply atomic refactoring steps per the guide. If any test fails after a step, revert immediately.
5. Report in the format that guide defines (smell addressed, techniques applied, before/after refs, test verification).
