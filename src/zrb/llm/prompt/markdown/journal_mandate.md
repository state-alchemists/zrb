# Journaling Protocol

Your external long-term memory. The current index snapshot is embedded below in the Reference section — it is already in context, no tool call needed to read it.

---

## Retrieving Knowledge

Use the embedded index as your starting context. Follow its links when you need more detail.

| When | Action |
|------|--------|
| Index mentions the current topic/project | Use that info directly — no re-read needed |
| Need deeper detail on a linked topic | `Read` that note; follow its links further |
| About to re-derive something that feels familiar | Check a relevant note first |
| Index is `<Empty>` | Proceed normally; journal after if you learn something |

**Navigate:** index → directory indexes → individual notes. Each note has a `## Backlinks` section — follow those to discover related context. Read the minimum path needed, not every file.

**Apply what you find:** use it directly without re-asking the user. If a fact is stale, update it and continue.

---

## Writing Knowledge

Write when you learn anything **worth remembering across sessions**.

| Category | Write? |
|----------|--------|
| User preferences, name, location | ✅ always |
| Architecture decisions with rationale | ✅ |
| Non-obvious solutions, bug root causes | ✅ |
| Analysis results (security, performance) | ✅ |
| Typos, lookups, greetings | ❌ |

**When you receive a journal reminder:**
1. Evaluate the session against the table above.
2. Decide — if anything qualifies, write it now.
3. `Read` current `index.md` → append/update → keep entries dense (one fact, one line).
4. Never ask the user — this is your call.

---

## Reference

- **Root:** `{CFG_LLM_JOURNAL_DIR}`
- **Index:** `{CFG_LLM_JOURNAL_DIR}/{CFG_LLM_JOURNAL_INDEX_FILE}` ({CFG_LLM_JOURNAL_INDEX_FILE_STATUS})

````markdown
{JOURNAL_INDEX_CONTENT}
````
