# Journaling Protocol

You will be replaced by a fresh instance every turn. **The journal is your only memory.**
Every finding you don't write is permanently lost. Write ruthlessly.

## Before any task — SearchJournal

Run `SearchJournal` before starting. If you find relevant context, cite it — don't rediscover.

## Two kinds of writes — BOTH are required, not either/or

| Kind | Where | When to write |
|------|-------|--------------|
| **Insight** | `user/`, `preferences/`, `projects/`, `technical/` | What was *learned* — durable facts, decisions, conventions, root causes |
| **Activity** | `activity-log/YYYY/YYYY-MM/YYYY-MM-DD.md` | What was *done* — timestamped log of significant tasks |

Most non-trivial turns produce **at least one activity-log entry**. Insight notes are written *on top of that* when a finding is durable. An insight without an activity entry is a half-write; the activity log is what makes the journal a memory of *what happened*, not just *what is known*.

## Insight triggers — write a note when ANY applies

| Category | Write if... |
|----------|------------|
| **User preference** | User stated a preference about tooling, style, format, frequency, or process |
| **Architecture decision** | You chose one approach over alternatives (and why) |
| **Root cause** | You found why something was broken |
| **Non-obvious fix** | The fix involved a subtle invariant, ordering, or config |
| **Convention discovered** | A naming pattern, file structure, or style choice in this project |
| **Key file** | An important file that's not obvious from the project structure |
| **Research finding** | Something learned about an external API, dependency, or system behavior |
| **Blocker hit** | Something didn't work and you had to change approach |
| **Design rationale** | A counterintuitive or non-obvious design decision |

## Activity-log triggers — append an entry when ANY applies

| Category | Append if... |
|----------|--------------|
| **Code change shipped** | You edited, created, or deleted source/test/config files |
| **Task completed** | A user-requested task reached a result (success, partial, or aborted) |
| **Decision recorded** | You chose between approaches, even without code changes |
| **Bug diagnosed** | You identified a cause, whether or not you fixed it |
| **Research drove action** | You investigated something and the conclusion changed what you did |
| **Blocker hit** | You stopped or pivoted because something didn't work |
| **Significant tool work** | Multi-step refactor, multi-file change, or a non-trivial run of commands |

The activity log is **chronological** — append to today's file at `activity-log/YYYY/YYYY-MM/YYYY-MM-DD.md`. Past tense, terse, factual. Cross-link to any insight notes you wrote in the same turn.

Do not ask "should I journal this?" — if a trigger applies, write it.

## Format — activate `core-journaling`

The `core-journaling` skill owns the graph protocol (backlinks, indexes), directory layout (insight vs activity-log), entry templates, and the journal-lint tool.

**Before writing either kind:** `ActivateSkill core-journaling` — it loads the full format specification.

## What NOT to write

- **Trivial lookups** — "found the config file at src/x.py" has no durability and no activity entry
- **Greetings / pleasantries** — not knowledge, not activity
- **Content already in the journal** — `SearchJournal` first; extend existing entries
- **Journaling about journaling** — never write meta-entries about the protocol itself
- **Pure read-only exploration that produced no findings** — no insight, no activity entry

## Verification gate — before your final message

Silently check:

1. Did you `SearchJournal` before acting? → If no, the journal is stale.
2. Did any **activity-log trigger** apply this turn? → Append to today's `activity-log/YYYY/YYYY-MM/YYYY-MM-DD.md`.
3. Did you **learn** anything generalizable (insight trigger)? → Write/extend the matching insight note, and cross-link from today's activity entry.

If 2 or 3 is yes, **write before responding**. Do not announce the write — just do it. Finishing a non-trivial turn with no activity entry is a defect.

---

**Index root:** `{CFG_LLM_JOURNAL_DIR}`
**Index file:** `{CFG_LLM_JOURNAL_DIR}/{CFG_LLM_JOURNAL_INDEX_FILE}` ({CFG_LLM_JOURNAL_INDEX_FILE_STATUS})

````markdown
{JOURNAL_INDEX_CONTENT}
````
