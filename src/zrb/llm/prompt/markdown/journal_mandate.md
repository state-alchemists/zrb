# Journaling Protocol

Maintain a structured knowledge graph as external long-term memory. Write after every session that produces non-trivial learning.

---

## When to Write

**Rule:** Journal when you learn **anything new worth remembering**. If the knowledge would help you or another agent work better in future sessions, write it.

| Category | Trigger | Examples | Skip? |
|----------|---------|----------|-------|
| **User Context** | User reveals preference or constraint | Name, location, communication style, tool choices, workflow preferences | ❌ Never |
| **Architecture** | Design decision with rationale | Chose X over Y (reason Z), new pattern adopted, system boundary defined | ❌ Never |
| **Technical Insight** | Non-obvious solution discovered | Bug required real investigation, workaround found, root cause identified | ❌ Never |
| **Analysis Results** | Investigation or review completed | Code quality scores, security audit findings, performance profiling results | ❌ Never |
| **Error Resolution** | Non-trivial error diagnosed and fixed | Multi-step diagnosis, cascading failures, environment-specific issues | ❌ Never |
| **Routine** | No new knowledge generated | Typo fix, simple lookup, file read, greeting, progress update | ✅ Always |

**Quick Test:** Ask "Would future-me or another agent work better knowing this?" If yes → journal.

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
