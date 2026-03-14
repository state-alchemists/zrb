# Journal Rules

## Scope: Tier-Aligned

| Tier | Journal? | Reason |
|------|----------|--------|
| **1-Trivial** | Skip | No learnings worth persisting |
| **2-Routine** | If learning | Write when you discover something new |
| **3-Architectural** | Yes | Document decisions and rationale |

## Pre-Response Check (Tier 2/3 Only)

After completing work, before responding, ask:

```
Did I discover anything worth persisting?
  - User preference revealed?
  - Architectural decision made?
  - Technical solution found?
  - Error/resolution discovered?

If YES → ActivateSkill("core-journaling") and update NOW
If NO  → Proceed with response
```

**Skip this check entirely for Tier 1 tasks.**

## Write Immediately

- ✅ "I learned something → journal now"
- ❌ "I'll journal later" → You WILL forget

## Journal-Worthy

| Category | Examples |
|----------|----------|
| User Preferences | Communication style, workflow preferences |
| Decisions | Architectural choices, technical selections |
| Technical Insights | Framework patterns, bug fixes, integrations |
| Errors & Resolutions | Root causes, fix procedures |

**Do NOT write for:** Trivial queries, simple lookups, public knowledge

## Reference

- **Root:** `{CFG_LLM_JOURNAL_DIR}` ({CFG_LLM_JOURNAL_DIR_STATUS})
- **Index:** `{CFG_LLM_JOURNAL_DIR}/{CFG_LLM_JOURNAL_INDEX_FILE}` ({CFG_LLM_JOURNAL_INDEX_FILE_STATUS})

````markdown
{JOURNAL_INDEX_CONTENT}
````