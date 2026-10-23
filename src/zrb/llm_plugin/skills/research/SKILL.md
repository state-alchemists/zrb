---
name: research
description: Force explicit research mode — Scope → Discover → Synthesize → Plan — with the approval gate before any implementation.
user-invocable: true
disable-model-invocation: true
preload: [core-research]
---
# /research

The user invoked `/research` with: $ARGUMENTS

Procedure:

1. This skill preloads `core-research`; its workflow and approval gate are above. If that `<ACTIVATED_SKILL>` block is missing, activate it now.
2. Treat the user's input as the research question. If the question is ambiguous or under-specified, complete the Scope step by asking once before discovering.
3. Apply the workflow. **Do not modify code** during Scope or Discovery. When running interactively, **do not begin implementation** until the user has explicitly approved the plan. When running non-interactively (no user to approve), present the plan inline and then proceed.
4. Deliver per the workflow's output standards: direct answer (for questions), Action → Target → Verification steps (for plans), or compared options with rationale (for decisions). Cite sources: `file:line` for code, URLs for web.
