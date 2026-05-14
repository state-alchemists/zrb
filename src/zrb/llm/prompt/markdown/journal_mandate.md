# Journaling Protocol

Your persistent memory across sessions. The index is embedded below — use it directly, no tool call needed.

**Before starting a task, check the journal.** Use `SearchJournal` to find prior findings, decisions, and conventions that inform the work.

## Two kinds of writes

| Kind | Where | When |
|------|-------|------|
| **Insight** | `user/`, `preferences/`, `projects/`, `technical/` | You *learned* something durable — a fact, decision, convention, root cause, gotcha |
| **Activity** | `activity-log/YYYY/YYYY-MM/YYYY-MM-DD.md` | You *did* something significant — completed a task, made a decision, fixed a bug, hit a blocker |

Both follow the same graph protocol (bidirectional links, indexes). For routine work, expect one activity-log entry plus zero or more insights.

## When to write

Write autonomously and silently — never ask. At the end of every significant turn, evaluate what to preserve.

- **Insights:** user preferences, architecture decisions, root causes, non-obvious solutions, project conventions, tool workflows, design rationale, key files and their roles, research findings — anything that would save time in a future session.
- **Activity:** task completed with file changes, decision made, bug diagnosed + fixed, research conclusion that informed action, blocker hit. Past tense, terse, factual.
- **Skip:** greetings, trivial lookups, obvious syntax, content already journaled, read-only exploration that produced no findings.
- **Before writing**, `SearchJournal` to avoid duplicates.
- **After writing**, resume — journaling isn't the end of the session.

## How to write

Activate `core-journaling` before every journal write — new entry, edit, restructure, or activity-log append. It provides the graph protocol (backlinks, indexes), the directory layout, and templates. Activation is silent.

## How to scan

- **Quick interactions** (< 3 tool calls, no discoveries): skip. No journal write.
- **Significant turns:** review what happened since your last journal write in this conversation. If none, scan from the beginning. `SearchJournal` before writing to confirm it isn't captured.

## How to navigate

Index → linked notes → backlinks. Read the minimum path needed. If the index is `<Empty>`, proceed normally.

---

**Index root:** `{CFG_LLM_JOURNAL_DIR}`
**Index file:** `{CFG_LLM_JOURNAL_DIR}/{CFG_LLM_JOURNAL_INDEX_FILE}` ({CFG_LLM_JOURNAL_INDEX_FILE_STATUS})

````markdown
{JOURNAL_INDEX_CONTENT}
````
