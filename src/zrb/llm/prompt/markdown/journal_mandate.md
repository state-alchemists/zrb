# Journaling Protocol

Your persistent long-term memory. The current index is embedded below — use it directly, no tool call needed.

## When to Write

Write if it would help future sessions: learned preferences, architectural decisions, root causes discovered, non-obvious solutions. Skip greetings, single lookups, sessions with no findings. Write silently — never ask the user before journaling.

When triggered by a journal reminder: if something qualifies, append one fact per line to `index.md`.

## How to Navigate

Index → linked notes → follow backlinks. Read the minimum path needed.

If the index is `<Empty>`, proceed normally.

---

**Index root:** `{CFG_LLM_JOURNAL_DIR}`
**Index file:** `{CFG_LLM_JOURNAL_DIR}/{CFG_LLM_JOURNAL_INDEX_FILE}` ({CFG_LLM_JOURNAL_INDEX_FILE_STATUS})

````markdown
{JOURNAL_INDEX_CONTENT}
````
