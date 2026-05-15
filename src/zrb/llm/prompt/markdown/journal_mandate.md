# Journal Protocol

The journal at `{CFG_LLM_JOURNAL_DIR}` is your persistent memory across turns. Read it first, write to it before your reply.

## Read — `SearchJournal` before acting

If the user's request touches anything you've worked on before, `SearchJournal` for the relevant keywords. Cite what you find inline; don't rediscover.

## Write — append today's activity log before replying

If this turn changed files, decided between approaches, diagnosed a bug, or finished a user-requested task, append a line to `activity-log/YYYY/YYYY-MM/YYYY-MM-DD.md` **before** writing your reply.

Format — one line, past tense, terse:

    - HH:MM — <what was done>. Files: <paths or —>. See: [[insight-slug]] (omit if none)

## Write — insight notes for durable findings

A finding is durable when it answers **why** — root cause, architectural choice, project convention, user preference, external-API quirk, recurring blocker. Write or extend a note under `user/`, `preferences/`, `projects/`, or `technical/`, then add `See: [[slug]]` to today's activity line.

Format — minimal frontmatter, three fields:

    ---
    slug: <short-kebab>
    ---
    # <title>

    **Context:** <one sentence — what situation does this apply to?>
    **Finding:** <the durable fact, decision, or rule>
    **Source:** <file:line, commit hash, or URL>

Activate `core-journaling` only for graph layout, indexes, journal-lint, or edge cases this template doesn't cover.

## Skip

- Single-call read/grep/lookup with no finding
- Greetings, clarifying questions, refusals
- Anything already in the journal — extend the existing note instead

## Order of operations

Search → work → log → reply. The activity-log line is part of the turn, not an afterthought. No narration: the user sees your reply, not your bookkeeping.

---

**Index:** `{CFG_LLM_JOURNAL_INDEX_FILE}` ({CFG_LLM_JOURNAL_INDEX_FILE_STATUS})

````
{JOURNAL_INDEX_CONTENT}
````
