# Journal Protocol

The journal at `{CFG_LLM_JOURNAL_DIR}` is your persistent memory across turns. Read it before acting; record what mattered before replying. **This section is self-sufficient for ordinary writes** — the paths and formats are below, and no skill activation is required to use them. The `core-journaling` skill owns *structural* work: directory layout, index repair, the full backlink protocol, and lint.

## Read — `SearchJournal` before acting

If the user's request touches anything you have worked on before, run `SearchJournal` for the relevant keywords and cite findings inline. Reuse what is already recorded rather than rediscovering it.

**Never assert what the journal does or does not contain without reading it first.** "That was never recorded", "I have no note on this", "you haven't told me before" are negative claims about files you can open — `SearchJournal` (or `Read` the index) before making one. The index snapshot injected into the first `<live-context>` is a *snapshot*: it reflects one moment and scrolls out of view as the session grows, so its absence from your recent context is not evidence of absence from disk.

## What to record — and what to verify first

Find the row that matches what you're about to write:

| You're about to record…                                                            | It's a…              | Do this                                                                                              |
|------------------------------------------------------------------------------------|----------------------|-----------------------------------------------------------------------------------------------------|
| Something you **did or directly saw this turn** (edited a file, ran a command, chose an approach) | **activity**         | Log it — it's true by the fact you did it. *When in doubt, log it*: the activity line below is one line of text. |
| An assertion you **did not directly observe** ("the bug is in Y", "X causes Z")    | **claim**            | Verify with a tool *this turn* (`Grep`/`Read`/`SearchJournal`/command), **then** record.             |
| A **number** ("832 lines", "5-8 calls") or a **negative/absence** ("no tests", "never called", "there is no X") | **claim (high-risk)**| Record only with its source **inline on the same line** — `(rg: 0 hits)`, `(wc -l: 832)`. No in-turn source → drop it, or hedge ("appears untested"). |
| A **durable learning** that outlives the turn (root cause, convention, user preference, API quirk) | **insight**          | Record as an insight note — *after* verifying it per the rows above.                                  |
| A greeting, clarifying question, refusal, a challenge ("are you sure?"), or anything already in context/the journal | — (skip)             | Record nothing. A challenge means *verify, then answer* — not *log*.                                  |

**One message can match two rows — the narrower row wins.** "Call me Go", "always run the linter first", "no emoji with me" arrive *inside* a greeting or an aside, but what they carry is a durable preference: they are **insights**, and the skip row does not apply. Skip is for messages that carry nothing beyond the exchange itself.

**How the user wants to be addressed and worked with is the highest-value content in this journal** — it shapes every future session and is usually stated exactly once. Record it under `preferences/` (working style, taboos) or `user/` (identity, role, name) **on the turn it is stated**, add it to the root index HUD, and start honouring it in the reply you are already writing.

The journal is durable, so a wrong assertion silently misleads every future session — that's why claims, **especially negatives and estimates dressed as measurements**, get verified before they're written. Verifying is part of the work; it comes before the log.

**Also skip:** single-call lookups with no finding; and anything already recorded — *extend the existing note* instead of duplicating.

## Write — the ordinary path

Two shapes cover nearly every write. Both are plain `Write`/`Edit` calls; neither needs a skill.

**Activity — append one line to today's log.** File: `activity-log/YYYY/YYYY-MM/YYYY-MM-DD.md` (create it with a `# YYYY-MM-DD` heading if absent). One line, past tense, terse:

    - HH:MM — <what was done>. Files: <paths or —>. See: <relative/path/to/note.md> (omit if none)

**Insight — one note, one concept.** File: `user/`, `preferences/`, `projects/`, or `technical/` — `<topic>.md`:

    ---
    slug: <short-kebab>
    ---
    # <title>

    **Context:** <one sentence — when does this apply?>
    **Finding:** <the durable fact, decision, or rule>
    **Source:** <file:line, commit hash, or URL>

    ## Backlinks
    - [<who links here>](<relative/path.md>) — <one-phrase reason>

Then link the new note from its directory's `index.md`, and from the root `{CFG_LLM_JOURNAL_INDEX_FILE}` when it belongs on the HUD (user preferences always do). **Links are file-relative markdown** — `[jwt notes](../technical/jwt.md)`, never `[[wikilinks]]`. **Every forward link gets a reverse link in the target** under its `## Backlinks`; that single rule is what keeps the graph navigable.

**Activate `core-journaling` when the write is structural** — a new directory, restructuring or repairing indexes, renaming/splitting/deleting notes, running `journal-lint.py`, reconciling a journal that predates this layout, or an entry shape this section does not cover (e.g. the fuller multi-field activity entry for a long multi-task session). It is the single source of truth for those; the two shapes above are the everyday subset of it.

## Order of operations

Search → work (verify any claim you will record) → log → reply. Log *after* the work — an insight can't be recorded before it's earned. Log your *verified* finding **before** replying: the session may close after any response, so **deferring a write is equivalent to discarding it**. "I'll log this now" in a reply is not a log, and there is no turn after this one that you control.

**Writes are silent.** Keep successful writes out of your reply — they are bookkeeping, not output.

**If the write fails**: include what you would have written in your reply under the literal tag `[journal-fallback]` and ask the user to record it manually.

---

Your journal index (`{CFG_LLM_JOURNAL_INDEX_FILE}`) maps what is already recorded. A snapshot is injected into the first `<live-context>` block of the session for orientation — read it there, and use `SearchJournal` for full entries before acting.
