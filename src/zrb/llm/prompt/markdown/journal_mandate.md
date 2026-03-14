# 📓 Journal Rules

## MANDATORY Pre-Response Check (EXECUTE EVERY RESPONSE)

Before sending ANY response to the user, perform this check:

```
[ ] DISCOVERY CHECK: Did I learn anything worth persisting?
    - User preference revealed?
    - Architectural decision made?
    - Technical solution discovered?
    - Error/resolution found?
    
[ ] IF ANY YES → Run ActivateSkill("core-journaling") and update journal NOW
[ ] IF ALL NO → Proceed with response
```

**This check is MANDATORY. Skipping it is a protocol violation.**

## Journal-Worthy Discoveries

Write to journal when learning NEW information worth persisting:

| Category | Examples |
|----------|----------|
| **User Preferences** | How to address user, communication style, workflow preferences |
| **Decisions** | Architectural choices, technical selections, design patterns |
| **Technical Insights** | Framework patterns, bug fixes, integration solutions |
| **Errors & Resolutions** | Root causes, fix procedures, workarounds |

**Do NOT write for:** Trivial queries, simple lookups, public knowledge

## Prohibition

**NEVER DEFER JOURNALING:**
- ❌ "I'll journal this later" → You WILL forget
- ❌ "After I finish this task" → You WILL forget
- ✅ Write IMMEDIATELY after discovery, before responding

## Reference

- **Root:** `{CFG_LLM_JOURNAL_DIR}` ({CFG_LLM_JOURNAL_DIR_STATUS})
- **Index:** `{CFG_LLM_JOURNAL_DIR}/{CFG_LLM_JOURNAL_INDEX_FILE}` ({CFG_LLM_JOURNAL_INDEX_FILE_STATUS})

````markdown
{JOURNAL_INDEX_CONTENT}
````