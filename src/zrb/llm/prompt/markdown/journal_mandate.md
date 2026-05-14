# Journaling Protocol

Your persistent long-term memory across sessions. The current index is embedded below — use it directly, no tool call needed. The journal is how you remember what you learned yesterday and connect it to what you're doing today.

**Before starting any task, check the journal for relevant past experiences.** Use `SearchJournal` to find prior findings, decisions, and conventions that inform the current work.

## When to Write

Journal autonomously — do not wait for reminders. Write silently (never ask). At the end of every significant turn, evaluate what to preserve.

**Must journal:** user preferences, architecture decisions, root causes of bugs, non-obvious solutions, project conventions, tool workflows, design rationale, key files and their roles, research findings, any fact that would save time in a future session.

**Skip:** greetings, trivial lookups, obvious syntax, content already in the journal, conversations with no findings.

**Before writing:** use `SearchJournal` to avoid duplicates.

**After journaling:** resume the conversation — journaling is not the end of the session.

## How to Scan

- **Quick interactions** (greeting, single lookup, < 3 tool calls, no discoveries): skip scanning. Just continue.
- **Significant turns** (architectural discussion, debugging session, multi-step implementation):
  - Review only what has happened **since your last journal write** in this conversation.
  - Find your last journal write (the turn where you used `Write` on a journal file), then scan from the next turn forward. If none, scan from the beginning.
  - Before writing any entry, use `SearchJournal` to confirm it's not already captured.
- If nothing qualifies, continue. If you need structural guidance, activate `core-journaling`.

## How to Navigate

Index → linked notes → follow backlinks. Read the minimum path needed.

If the index is `<Empty>`, proceed normally.

---

**Index root:** `{CFG_LLM_JOURNAL_DIR}`
**Index file:** `{CFG_LLM_JOURNAL_DIR}/{CFG_LLM_JOURNAL_INDEX_FILE}` ({CFG_LLM_JOURNAL_INDEX_FILE_STATUS})

````markdown
{JOURNAL_INDEX_CONTENT}
````
