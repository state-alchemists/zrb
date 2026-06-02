# Insight Note Template

An insight note records what was *learned* — a durable fact, decision, or rule. It lives under `user/`, `preferences/`, `projects/`, or `technical/`, one concept per file. Use the format below.

## Format

````markdown
---
slug: <short-kebab>
---
# <title>

**Context:** <one sentence — when does this apply?>
**Finding:** <the durable fact, decision, or rule>
**Source:** <file:line, commit hash, or URL>

## Backlinks
- [<linking note or activity entry>](<relative/path.md>) — <one-phrase reason>
````

## Rules

- **One concept per file.** If a note grows past ~80 lines or covers two ideas, split it.
- **Frontmatter `slug`** is a short kebab-case identifier, independent of the filename.
- **Every note carries a `## Backlinks` section.** When you add a forward link in the body, immediately append a reciprocal backlink in the target file (see the Graph Protocol in `SKILL.md`).
- **Links are standard markdown** `[text](path.md)` relative to the journal root — never `[[wikilinks]]`. The journal-lint tool only recognizes markdown links.
- **Durable only.** Reserve insight notes for root causes, architectural choices, project conventions, user preferences, external-API quirks, or recurring blockers. Routine task logs belong in the activity log, not here.

## After Writing

Run `tools/journal-lint.py` (see `SKILL.md` → Companion Tools) to verify backlinks resolve and the note is reachable from an `index.md` — a new note with no inbound link is an orphan.

## Example

````markdown
---
slug: llm-task-system-prompt-hook
---
# LLMTask exposes get_system_prompt for testing

**Context:** When a test needs to assert on the composed system prompt without running an agent.
**Finding:** `LLMTask` exposes `get_system_prompt(ctx)` as a public hook; tests call it directly instead of patching internals.
**Source:** src/zrb/llm/task/llm_task.py:212

## Backlinks
- [activity-log/2026/2026-06/2026-06-02](../activity-log/2026/2026-06/2026-06-02.md) — introduced during the prompt refactor
````
