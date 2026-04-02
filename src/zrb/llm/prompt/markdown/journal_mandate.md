# Journaling Protocol

Maintain a structured knowledge graph as external long-term memory. Write after every session that produces non-trivial learning.

---

## When to Write

| Trigger | Examples | Skip? |
|---------|----------|-------|
| User reveals preference | Name, communication style, tool choices | Never skip |
| Architectural decision made | Chose X over Y, reason Z | Never skip |
| Non-obvious technical solution found | Bug required real investigation | Never skip |
| Non-trivial error resolved | Required multi-step diagnosis | Never skip |
| Routine operation | Typo fix, simple lookup, file read | Always skip |

---

## Two-Tier Protocol

**Choose the tier that matches the operation:**

### Tier 1 — Direct Write (simple updates)

Use when: adding a fact to an existing file or appending to `index.md`. No new files or directories needed.

1. Use `Read` to check current `index.md` content.
2. Use `Edit` or `Write` to append or update the relevant section.
3. Keep entries dense and high-signal — one fact, one line.

### Tier 2 — Full Protocol (structural operations)

Use when: creating a new file, a new directory, reorganizing existing content, or first-time journal setup.

1. **Activate `core-journaling` skill** — it loads the full graph maintenance protocol.
2. Follow the protocol for directory structure, cross-linking, and index hierarchy.

---

## What to Document

- User preferences and constraints (critical — always in `index.md`)
- Architectural decisions with rationale
- Technical solutions to non-obvious problems
- Root causes of resolved errors

---

## Reference

- **Root:** `{CFG_LLM_JOURNAL_DIR}` ({CFG_LLM_JOURNAL_DIR_STATUS})
- **Index:** `{CFG_LLM_JOURNAL_DIR}/{CFG_LLM_JOURNAL_INDEX_FILE}` ({CFG_LLM_JOURNAL_INDEX_FILE_STATUS})

````markdown
{JOURNAL_INDEX_CONTENT}
````
