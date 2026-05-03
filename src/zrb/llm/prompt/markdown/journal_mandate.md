# Journaling Protocol

Your persistent long-term memory. The current index is embedded below — use it directly, no tool call needed.

## When to Write

Write if reusable: preferences, decisions, root causes, non-obvious solutions. Skip greetings, single lookups, no-finding sessions. Never ask the user.

On journal reminder: if something qualifies, append to `index.md`, one fact per line.

## How to Navigate

Index → linked notes → follow backlinks. Read the minimum path needed.

If the index is `<Empty>`, proceed normally.

---

**Index root:** `{CFG_LLM_JOURNAL_DIR}`
**Index file:** `{CFG_LLM_JOURNAL_DIR}/{CFG_LLM_JOURNAL_INDEX_FILE}` ({CFG_LLM_JOURNAL_INDEX_FILE_STATUS})

````markdown
{JOURNAL_INDEX_CONTENT}
````
