# 📓 Journal Rules

## Protocol
1. **Activate:** Run `ActivateSkill("core-journaling")` before any journal operation.
2. **Read:** Before tasks involving user preferences, project conventions, or architectural decisions.
3. **Write:** After discovering user preferences, decisions, completions, errors, or corrections.
4. **Timing:** Update BEFORE responding to user.

## When to Write (Examples)
Write to journal when learning new information worth persisting:
- **User Preferences:** How user wants to be addressed, communication style, workflow preferences
- **Decisions:** Significant architectural or technical choices made during session
- **Errors & Corrections:** Important failures, root causes, and their resolutions
- **Session Insights:** Key takeaways valuable for future sessions

Do NOT write for trivial queries (e.g., "What time is it?", simple lookups).

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
