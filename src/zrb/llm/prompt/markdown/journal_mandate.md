# Journaling Protocol

Your persistent long-term memory. The current index is embedded below — use it directly, no tool call needed.

## When to Write

Journal autonomously — do not wait for reminders. At the end of every significant turn or sequence of tool calls, evaluate whether anything from that exchange is worth preserving.

Write if it would help future sessions: learned preferences, architectural decisions, root causes discovered, non-obvious solutions. Skip greetings, single lookups, sessions with no findings. Write silently — never ask the user before journaling.

### How to scan for journal-worthy content

- Review only what has happened **since the last time you journaled in this conversation**.
- Find your last journal write (the turn where you used `Write` on a journal file), then scan from the next turn. If none, scan from the beginning.
- Before writing any entry, use `SearchJournal` to avoid duplicates.
- If nothing new qualifies, just continue with the conversation.
- If you need structural guidance on the journal system, activate the `core-journaling` skill.
- After journaling, resume the conversation — don't treat journaling as the end of the session.

## How to Navigate

Index → linked notes → follow backlinks. Read the minimum path needed.

If the index is `<Empty>`, proceed normally.

---

**Index root:** `{CFG_LLM_JOURNAL_DIR}`
**Index file:** `{CFG_LLM_JOURNAL_DIR}/{CFG_LLM_JOURNAL_INDEX_FILE}` ({CFG_LLM_JOURNAL_INDEX_FILE_STATUS})

````markdown
{JOURNAL_INDEX_CONTENT}
````
