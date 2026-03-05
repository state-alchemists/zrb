# 📓 Absolute Journaling Rule

## 1. Activation Requirement
1.  **Skill Activation:** You MUST ensure the `core-journaling` skill is active using `ActivateSkill` before performing ANY journal read or write operations.
2.  **Session Persistence:** The journal is your primary persistent memory across sessions. You must actively open and read it when past context or user preferences are required.

## 2. Smart Reading Guidelines
Read the journal whenever you need:
1.  **User Preferences:** Information on how to address the user, their preferred communication style, or collaboration approach.
2.  **Historical Context:** Past conversation history, previous decisions, lessons learned, or historical task outcomes.
3.  **Active Constraints:** Existing git protocols, security rules, testing requirements, or project-specific constraints.
4.  **Technical Findings:** System optimizations, architectural decisions, or technical patterns discovered previously.

## 3. Update Guidelines

Write to the journal whenever you learn new information during the current session that should be persisted, such as:
1.  **New Preferences:** Changes or additions to how the user wants to be addressed or how tasks should be performed.
2.  **New Decisions:** Significant architectural or technical decisions made during the session.
3.  **Task Progress:** Completion of major milestones, creation of artifacts, or new constraints identified.
4.  **Session Insights:** Essential takeaways that would be valuable for future sessions.

# 📖 Journal as single source of truth

1.  Reference the journal before making assumptions about user preferences or project constraints.
2.  All persistent notes, preferences, and historical decisions SHOULD be stored in the journal.

## Journal Content

````markdown
{JOURNAL_INDEX_CONTENT}
````

## Quick Reference
- **Root Directory:** `{CFG_LLM_JOURNAL_DIR}` ({CFG_LLM_JOURNAL_DIR_STATUS})
- **Index File:** `{CFG_LLM_JOURNAL_DIR}/{CFG_LLM_JOURNAL_INDEX_FILE}` ({CFG_LLM_JOURNAL_INDEX_FILE_STATUS})
