# 📓 Journal Rules

## Protocol
1. **Activate:** Run `ActivateSkill("core-journaling")` before any journal operation.
2. **Read:** Before tasks involving user preferences, project conventions, or architectural decisions.
3. **Write:** After discovering user preferences, decisions, completions, errors, or corrections.
4. **Timing:** Update BEFORE responding to user.

## Prohibitions
1. **NEVER** defer journal entries—entries not written immediately are lost.

## Hierarchy
Journal content overrides assumptions within the journal domain. General mandates (secrets, cancellation, ambiguity) always apply.

## Reference
- **Root:** `{CFG_LLM_JOURNAL_DIR}` ({CFG_LLM_JOURNAL_DIR_STATUS})
- **Index:** `{CFG_LLM_JOURNAL_DIR}/{CFG_LLM_JOURNAL_INDEX_FILE}` ({CFG_LLM_JOURNAL_INDEX_FILE_STATUS})

````markdown
{JOURNAL_INDEX_CONTENT}
````
