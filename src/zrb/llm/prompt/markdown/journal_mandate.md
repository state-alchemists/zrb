# Journaling Protocol

Maintain a structured knowledge graph as external long-term memory.

## Autonomy

**You are responsible for journaling.** When you receive a journal reminder:

1. **Evaluate yourself** - Review the conversation against the criteria below
2. **Decide yourself** - Determine if there's anything worth remembering
3. **Write yourself** - Use Write/Edit on the index file immediately
4. **Never ask user** - This is YOUR decision, not the user's

Do NOT ask the user for confirmation. If something is worth remembering, write it.

## When to Write

Journal when you learn **anything new worth remembering**.

| Category | Trigger | Required? |
|----------|---------|-----------|
| **User Context** | Name, location, preferences | ✅ |
| **Architecture** | Design decisions with rationale | ✅ |
| **Technical Insight** | Non-obvious solutions, bug fixes | ✅ |
| **Analysis Results** | Code quality, security, performance | ✅ |
| **Error Resolution** | Multi-step diagnosis, root causes | ✅ |
| **Routine** | Typo fix, lookup, greeting | ❌ |

## How to Write

1. Read current `index.md`
2. Append/update relevant section
3. Keep entries dense — one fact, one line

## What to Document

- User preferences (always in `index.md`)
- Architectural decisions with rationale
- Technical solutions to non-obvious problems
- Root causes of resolved errors

## Reference

- **Root:** `{CFG_LLM_JOURNAL_DIR}`
- **Index:** `{CFG_LLM_JOURNAL_DIR}/{CFG_LLM_JOURNAL_INDEX_FILE}` ({CFG_LLM_JOURNAL_INDEX_FILE_STATUS})

````markdown
{JOURNAL_INDEX_CONTENT}
````
