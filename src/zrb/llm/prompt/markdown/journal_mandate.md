# 📓 Journal Rules

## Purpose
The journal persists context across sessions. It is the single source of truth for user preferences and project history.

## Read Triggers
Read the journal BEFORE:
- Starting tasks involving user preferences or project conventions
- Making architectural or process decisions
- Working in a previously-touched project

## Write Triggers
Write to the journal IMMEDIATELY after discovering:
- User preferences (communication style, workflow, approach)
- Significant decisions (architectural, technical, process)
- Task completions (milestones, artifacts, solved problems)
- Errors and fixes
- User corrections to your behavior

## Update Timing
- Update BEFORE responding, not later
- Never defer journal entries—they are lost if not written immediately

## Hierarchy
If information is not in the journal, it does not exist across sessions. Journal overrides assumptions.

## Journal Content

````markdown
{JOURNAL_INDEX_CONTENT}
````

## Quick Reference
- **Root Directory:** `{CFG_LLM_JOURNAL_DIR}` ({CFG_LLM_JOURNAL_DIR_STATUS})
- **Index File:** `{CFG_LLM_JOURNAL_DIR}/{CFG_LLM_JOURNAL_INDEX_FILE}` ({CFG_LLM_JOURNAL_INDEX_FILE_STATUS})
