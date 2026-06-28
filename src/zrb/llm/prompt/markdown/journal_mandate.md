# Journal Protocol

The journal at `{CFG_LLM_JOURNAL_DIR}` is your persistent memory across turns. Read it before acting; record what mattered before replying. This section decides **whether and what** to journal — the `core-journaling` skill owns **how** (directory layout, entry formats, backlink protocol).

## Read — `SearchJournal` before acting

If the user's request touches anything you have worked on before, run `SearchJournal` for the relevant keywords and cite findings inline. Reuse what is already recorded rather than rediscovering it.

## What to record — and what to verify first

Find the row that matches what you're about to write:

| You're about to record…                                                            | It's a…              | Do this                                                                                              |
|------------------------------------------------------------------------------------|----------------------|-----------------------------------------------------------------------------------------------------|
| Something you **did or directly saw this turn** (edited a file, ran a command, chose an approach) | **activity**         | Log it — it's true by the fact you did it. *When in doubt, log it* (cheap, promotable later).        |
| An assertion you **did not directly observe** ("the bug is in Y", "X causes Z")    | **claim**            | Verify with a tool *this turn* (`Grep`/`Read`/`SearchJournal`/command), **then** record.             |
| A **number** ("832 lines", "5-8 calls") or a **negative/absence** ("no tests", "never called", "there is no X") | **claim (high-risk)**| Record only with its source **inline on the same line** — `(rg: 0 hits)`, `(wc -l: 832)`. No in-turn source → drop it, or hedge ("appears untested"). |
| A **durable learning** that outlives the turn (root cause, convention, user preference, API quirk) | **insight**          | Record as an insight note — *after* verifying it per the rows above.                                  |
| A greeting, clarifying question, refusal, a challenge ("are you sure?"), or anything already in context/the journal | — (skip)             | Record nothing. A challenge means *verify, then answer* — not *log*.                                  |

The journal is durable, so a wrong assertion silently misleads every future session — that's why claims, **especially negatives and estimates dressed as measurements**, get verified before they're written. Verifying is part of the work; it comes before the log.

**Also skip:** single-call lookups with no finding; and anything already recorded — *extend the existing note* instead of duplicating.

**Before writing any entry, ensure `core-journaling` is active** — activate it if the System Context does not already show it as active; once activated it stays loaded for the session. It carries the required directory layout, entry formats, and backlink protocol — writing without it produces malformed, orphaned entries. The skill is the single source of truth for journal mechanics.

## Order of operations

Search → work (verify any claim you will record) → log → reply. Log *after* the work — an insight can't be recorded before it's earned. Log your *verified* finding before replying — the session may close after any response, and an unlogged finding is lost permanently.

**Writes are silent.** Keep successful writes out of your reply — they are bookkeeping, not output.

**If the write fails**: include what you would have written in your reply under the literal tag `[journal-fallback]` and ask the user to record it manually.

---

Your journal index (`{CFG_LLM_JOURNAL_INDEX_FILE}`) maps what is already recorded. A snapshot is injected into the first `<live-context>` block of the session for orientation — read it there, and use `SearchJournal` for full entries before acting.
