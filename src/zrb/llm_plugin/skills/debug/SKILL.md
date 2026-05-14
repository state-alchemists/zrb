---
name: debug
description: Systematic diagnosis for broken builds or wrong behavior — reproduce, isolate, hypothesize, fix. Use when the user explicitly wants help diagnosing a failure.
user-invocable: true
disable-model-invocation: true
---
# /debug

The user invoked `/debug` with: $ARGUMENTS

Procedure:

1. Ensure `core-coding` is activated for this session. If you can't recall its companion layout from earlier, re-activate via `ActivateSkill('core-coding')` — silent and auto-approved.
2. Among `core-coding`'s companion files, locate the debug methodology guide and Read it.
3. Determine failure type from the user's input (build/compilation error vs runtime/behavioral). If unclear, ask once.
4. Follow the matching section in the guide. Do not skip the reproduction step for behavioral failures — confirm a reliable repro before hypothesizing.
5. Report findings in the format that guide defines (failure type, root cause, evidence, fix, verification).
