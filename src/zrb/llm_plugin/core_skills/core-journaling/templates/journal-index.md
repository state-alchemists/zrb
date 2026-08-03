# Root Index (HUD) Template

The root `index.md` is the only journal file injected into the conversation — first turn and each summarization. Everything else is found by searching. So this file carries **facts, compressed**, and links only where a link is genuinely all that is needed.

It is also the graph's root: `journal-lint.py` treats any file not reachable from here by following links as an orphan. So the HUD does two jobs — it states the facts that must survive without a search, *and* it is the entry point to everything else. `## Directories` is what does the second job.

## Format

````markdown
# Journal

## User

- **Name:** <what to call them> — <role / working context>
- <anything else that identifies them, one line each>

## Preferences

- <how they want to be worked with, one line>
- <a taboo, one line>

## Active Constraints

- <what is currently true and binding> — <until when, if it expires>

## Directories

- [user](user/index.md) · [preferences](preferences/index.md) · [projects](projects/index.md) · [technical](technical/index.md) · [activity-log](activity-log/index.md)

## Recent Insights

- [<title>](<relative/path.md>) — <one phrase>
````

## Rules

- **Order is fixed, and the reason is truncation.** The injected snapshot is capped at `LLM_JOURNAL_INDEX_MAX_CHARS` and overflow is dropped from the **end**. `User` and `Preferences` are small and near-static. `Directories` is one line and never grows. `Recent Insights` grows without bound, so it goes last — that way growth only ever evicts itself.
- **Truncation never breaks the graph.** The cap applies to the injected *snapshot*, not the file. `journal-lint.py` reads the file, so a `## Directories` line cut from context still keeps every directory reachable on disk.
- **One line per entry.** The detail lives in the note; the HUD holds the part that has to survive without anyone searching for it.
- **State the fact, don't link to it — in sections 1–3.** `- Prefers terse replies, no preamble.` beats a link to `preferences/tone.md`, because a link still has to be followed to do anything. Sections 4 and 5 are the exception and exist to be links: they carry reachability, not content.
- **Every directory index appears under `## Directories`.** Adding a new top-level directory to the journal means adding it here in the same turn, or everything under it is an orphan.
- **Promote and prune.** A recent insight that turns out to be permanent moves up into `Preferences` or `Active Constraints` and loses its link. One that goes stale is deleted. A constraint that expires is deleted, not annotated.
- **Empty sections stay.** An empty `## Preferences` heading tells the next session the slot exists and is unfilled; a missing one reads as "not applicable here".
- **A hand-shaped HUD wins.** If the user has given this file custom headings or their own ordering, keep their shape and add to it (see `SKILL.md` → Legacy Journals). This template is for a HUD you are creating, not a licence to reformat theirs.

## After Writing

Run `tools/journal-lint.py` (see `SKILL.md` → Companion Tools). A HUD missing `## Directories` lints as one orphan per top-level directory.

## Example

````markdown
# Journal

## User

- **Name:** Go — maintainer of zrb, works in a terminal, Indonesian/English.
- Runs the test suite themselves; hand back results rather than invoking it.

## Preferences

- Terse replies. No preamble, no summary of what was just said.
- Wants pushback on wrong approaches, not agreement.
- Clean breaks on renames — no back-compat shims.

## Active Constraints

- Python 3.14 on WSL2; no audio device, so hook subprocesses hang.

## Directories

- [user](user/index.md) · [preferences](preferences/index.md) · [projects](projects/index.md) · [technical](technical/index.md) · [activity-log](activity-log/index.md)

## Recent Insights

- [delegate agent naming](technical/delegate-agent-naming.md) — roster lives in the tool schema
- [prompt profile resolution](technical/prompt-profiles.md) — `auto` keys off declared model size
````
