# Activity Log Entry Template

A single day's file (`activity-log/YYYY/YYYY-MM/YYYY-MM-DD.md`) holds *multiple* entries — one per significant task. Each entry follows the format below.

## Per-Entry Format

````markdown
## HH:MM — <one-line task title>
**Request**: <one sentence summarizing what the user asked>
**Skills used**: <comma-separated list, e.g. core-coding, core-research; or "none" if no skill was activated>
**Actions**:
- <significant change — file path, command, or decision>
- <another>
**Outcome**: <completed | blocked: <reason> | awaiting user: <on what>>
**Cross-links**: [technical/<topic>](technical/<topic>.md) · [projects/<project>](projects/<project>.md)    <!-- omit line if no cross-links -->
````

## File-Level Boilerplate

The day file as a whole:

````markdown
# YYYY-MM-DD

## HH:MM — First task title
...

## HH:MM — Second task title
...

## Backlinks
- [activity-log/YYYY/YYYY-MM](../index.md)
````

The `## Backlinks` section at the bottom of the day file points to the parent month index. Insight notes that cross-link to a day file should append the day file's path under their own `## Backlinks` section (per the graph protocol).

## What Counts as a "Significant Task"

**Log:**
- Completed work that changed files (edits, refactors, new code)
- Decisions made (architecture, library choice, scope cuts)
- Bugs diagnosed and fixed — root cause noted
- Research conclusions that informed action
- Blockers hit (and the unblock plan, if any)
- Process-level events: "started feature X", "shipped PR Y"

**Skip:**
- Greetings, status checks, single-fact lookups
- Pure read-only exploration that produced no findings or decision
- Reads/searches whose result was already captured in an earlier entry the same turn

## Tone

Past tense, terse, factual. Treat it as evidence for your future self — not narrative.

- Good: "Refactored `LLMTask._create_agent` to expose `get_system_prompt`; 1,621 tests pass."
- Bad: "I started by looking at the LLMTask class, and after some thought I decided…"

## Example

````markdown
## 14:23 — Skill restructure: core-coding companions
**Request**: Make user-invocable skills depend on core skills via companion files.
**Skills used**: core-coding, core-design
**Actions**:
- Created `src/zrb/llm_plugin/skills/core-coding/workflows/{testing,debug,refactor,review}.md`
- Rewrote 4 top-level skill SKILL.md files as thin user wrappers
- Removed `research-and-plan/`, added `research/SKILL.md`
**Outcome**: completed; 1,621 LLM tests pass
**Cross-links**: [projects/zrb](projects/zrb.md) · [technical/skill-architecture](technical/skill-architecture.md)
````
