# Journaling Protocol

Document learning and decisions after completing tasks.

---

## When to Write

Journal when any of these conditions are met:

| Trigger | Examples |
|---------|----------|
| User reveals preference | Preferred name/location, communication style |
| Architectural decision made | Chose X over Y for reason Z |
| Technical solution found | Solved non-obvious bug, discovered efficient approach |
| Error resolved and non-trivial | Debugging required investigation, not just typo fix |

Skip for: typos, simple lookups, routine file edits, straightforward questions.

## Before Writing

**Activate `core-journaling` skill first.** This loads the full protocol for maintaining the journal as a structured knowledge graph.

## What to Document

- User preferences revealed
- Architectural decisions made
- Technical solutions found
- Errors and how resolved

---

## Reference

- **Root:** `{CFG_LLM_JOURNAL_DIR}` ({CFG_LLM_JOURNAL_DIR_STATUS})
- **Index:** `{CFG_LLM_JOURNAL_DIR}/{CFG_LLM_JOURNAL_INDEX_FILE}` ({CFG_LLM_JOURNAL_INDEX_FILE_STATUS})

````markdown
{JOURNAL_INDEX_CONTENT}
````
