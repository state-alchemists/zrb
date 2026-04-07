Review this session for journal-worthy learnings and update the journal if needed.

## Journal Location

- **Root:** `{CFG_LLM_JOURNAL_DIR}` ({CFG_LLM_JOURNAL_DIR_STATUS})
- **Index:** `{CFG_LLM_JOURNAL_DIR}/{CFG_LLM_JOURNAL_INDEX_FILE}` ({CFG_LLM_JOURNAL_INDEX_FILE_STATUS})

## Current Index

````markdown
{JOURNAL_INDEX_CONTENT}
````

## Graph Structure

The journal is a **graph-based knowledge base**. Follow these rules:

```
{CFG_LLM_JOURNAL_DIR}/
├── index.md           # Heads-Up Display (start here)
├── user/index.md
├── preferences/index.md
├── projects/index.md
├── technical/index.md
└── activity-log/      # YYYY/YYYY-MM/YYYY-MM-DD/
```

1. **RHIZOMATIC LINKING** — Link liberally between related concepts
2. **NO ORPHANS** — Every file MUST be reachable from `index.md`
3. **ATOMICITY** — One concept per file; split if a file grows large

Each directory MUST have its own `index.md` linking to all files inside it.

## What to Journal

| Worth journaling | Skip |
|-----------------|------|
| User preferences | Trivial lookups |
| Architecture decisions with rationale | Greetings |
| Non-obvious technical insights | Routine tasks |
| Bug root causes | Simple Q&A |
| Analysis results (code quality, security) | |

## Action

1. **Evaluate** — Did this session produce anything non-trivial worth remembering?
2. **Decide** — Make the call yourself. Do NOT ask the user.
3. **Write** — Use Write/Edit on the relevant journal files immediately.

If nothing is worth journaling, acknowledge briefly: "No journal updates needed."
