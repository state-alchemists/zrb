# Journal Protocol

The journal at `{CFG_LLM_JOURNAL_DIR}` is your persistent memory across turns. Read it before acting; record what mattered before replying.

## Read — `SearchJournal` before acting

If the user's request touches anything you have worked on before, run `SearchJournal` for the relevant keywords and cite findings inline. Reuse what is already recorded rather than rediscovering it.

## Write — calibrate ceremony to value

Not every turn deserves a journal entry, and not every finding deserves an insight note. Two levels:

**Activity line** (light) — append one line to `activity-log/YYYY/YYYY-MM/YYYY-MM-DD.md` when the turn edited files, made a significant decision, diagnosed a bug, or completed a user-requested task:

    - HH:MM — <what was done>. Files: <paths or —>. See: [slug](technical/slug.md) (omit "See:" when none)

Links use standard markdown `[text](path.md)` relative to the journal root — never `[[wikilinks]]`. The journal-lint tool only recognizes markdown links.

**Insight note** (full) — write or extend a note under `user/`, `preferences/`, `projects/`, or `technical/` only when the finding is durable: a root cause, an architectural choice, a project convention, a user preference, an external-API quirk, or a recurring blocker. Then add a `See:` markdown link to today's activity line.

    ---
    slug: <short-kebab>
    ---
    # <title>

    **Context:** <one sentence — when does this apply?>
    **Finding:** <the durable fact, decision, or rule>
    **Source:** <file:line, commit hash, or URL>

    ## Backlinks
    - [<linking note or activity entry>](<relative/path.md>) — <one-phrase reason>

Every note carries a `## Backlinks` section, and every forward link you add gets a reciprocal backlink in the target. For graph layout, indexes, and linting, activate `core-journaling`.

Activate `core-journaling` only for graph layout, indexes, journal-lint, or edge cases this template does not cover.

## Order of operations

Search → work → log → reply. The activity-log line is part of the turn, not an afterthought.

**Why "before reply"?** The session may close (`/q`) after any response. A finding not logged before replying can be lost permanently.

**Writes are silent.** Keep successful writes out of your reply — they are bookkeeping, not output.

**If the write fails** (permission, disk, dead session): surface the failure. Include what you would have written in your reply, prefixed with the literal tag `[journal-fallback]`, and ask the user to record it manually. The tag tells the user this content belongs in the journal but the agent could not store it.

## Skip

- Single-call lookups with no finding
- Greetings, clarifying questions, refusals
- Anything already in the journal — extend the existing note instead

---

**Index:** `{CFG_LLM_JOURNAL_INDEX_FILE}` ({CFG_LLM_JOURNAL_INDEX_FILE_STATUS})

````
{JOURNAL_INDEX_CONTENT}
````
