---
name: core-journaling
description: "Ensure this skill is active before every journal write — new entry, edit, restructure, or activity log append. Provides the graph protocol (bidirectional links, indexes), the directory layout, and the activity log format that keep the journal consistent."
user-invocable: false
---
# Skill: core-journaling

The Journal is a bidirectional graph knowledge base plus a chronological log book. Every note links to related notes; every link has a reverse (backlink). The root `index.md` is your Heads-Up Display. The `activity-log/` subtree records what was done over time.

**Ensure this skill is active before every journal write** — once activated it stays loaded for the session, so checking costs nothing (the System Context shows active skills). Skipping the protocol on "small" writes is how the journal becomes a half-graph: some notes linked, others orphaned. The graph protocol IS the routine — not a special mode.

## Directory Structure

```
<journal-root>/                         # CFG_LLM_JOURNAL_DIR
├── index.md                            # HUD: critical user prefs, active constraints, recent insights
├── user/
│   ├── index.md
│   └── <topic>.md                      # who the user is — role, context, history
├── preferences/
│   ├── index.md
│   └── <topic>.md                      # collaboration preferences, taboos
├── projects/
│   ├── index.md
│   └── <project>.md                    # per-project facts, decisions, layout
├── technical/
│   ├── index.md
│   └── <topic>.md                      # cross-project know-how, patterns, gotchas
└── activity-log/                       # chronological log of significant LLM actions
    ├── index.md                        # links each year
    └── YYYY/
        ├── index.md                    # links each month
        └── YYYY-MM/
            ├── index.md                # links each day
            └── YYYY-MM-DD.md           # all entries for that day
```

Each directory MUST have an `index.md` that links to every file in it. Exception: date-leaf directories under `activity-log/YYYY/YYYY-MM/` do not — the month index covers them.

## Two Kinds of Writes

| Kind | Where | Purpose |
|------|-------|---------|
| **Insight** | `user/`, `preferences/`, `projects/`, `technical/` | What was *learned* — durable facts, decisions, conventions |
| **Activity** | `activity-log/YYYY/YYYY-MM/YYYY-MM-DD.md` | What was *done* — timestamped log of significant tasks |

Both apply the graph protocol below. Both can cross-link to each other.

## Graph Protocol

### Link Convention

Use standard markdown links for all internal references. **Paths are relative to the file that contains the link** (standard markdown semantics) — climb out of a subdirectory with `../`:

- From the root `index.md`: `[asyncio patterns](technical/python-asyncio.md)`
- From `projects/my-app.md` to a technical note: `[jwt notes](../technical/jwt.md)`
- From an `activity-log/YYYY/YYYY-MM/` day file to a project note: `[zrb project](../../../projects/zrb.md)`

`journal-lint.py` resolves links this way. A link written relative to the journal root resolves correctly only from the root `index.md`; from any other file it is flagged as a broken link.

### Backlink Rule (Non-negotiable)

Every note (except `index.md` files) **must** have a `## Backlinks` section at the bottom. When you create a forward link, immediately append a backlink to the target. Backlink paths are file-relative too — written from the note that holds them.

For example, inside `technical/jwt.md`:

````markdown
## Backlinks
- [my-app project](../projects/my-app.md) — referenced for auth architecture
- [2026-06-02 log](../activity-log/2026/2026-06/2026-06-02.md) — algorithm chosen here
````

Rules:
1. Add a backlink immediately when you create a forward link.
2. When deleting a link, remove the corresponding backlink in the target.
3. Keep backlink entries short — path + one-phrase reason.

### Graph Invariants

1. **BIDIRECTIONAL** — every forward link has a backlink entry in the target.
2. **NO ORPHANS** — every file is reachable from `index.md` via forward links.
3. **ATOMICITY** — one concept per file; split if too large.
4. **RHIZOMATIC** — link liberally between related concepts across directories.

## Companion Templates

When writing a specific kind of entry, Read the matching template from this skill's directory:

| Writing | Template |
|---------|----------|
| An insight note (`user/`, `preferences/`, `projects/`, `technical/`) | `templates/insight-note.md` |
| A day's activity log entry | `templates/activity-entry.md` |

## Companion Tools

- `tools/journal-lint.py` — validates backlinks, finds orphans, reports broken paths. Run via `Shell` periodically and after structural changes:
  ```
  python <skill-dir>/tools/journal-lint.py <journal-root>
  ```

## Writing an Insight Note (Step-by-Step)

1. Decide the file path under `user/`, `preferences/`, `projects/`, or `technical/` (atomic — one concept per file).
2. Write the note body using the format in `templates/insight-note.md`.
3. Add forward markdown links to related notes throughout the body.
4. Add a `## Backlinks` section at the bottom (initially empty, or pre-populated if you know who will link here).
5. For each forward link you added, open the target file and append this note to its `## Backlinks` section.
6. Add a markdown link to the new note from the relevant directory `index.md`.
7. If noteworthy enough for the HUD, also add a link from outer `index.md` under *Recent Insights*.

## Writing an Activity Log Entry (Step-by-Step)

1. Compute today's path: `activity-log/YYYY/YYYY-MM/YYYY-MM-DD.md`.
2. If the file does not exist, create it with an `# YYYY-MM-DD` heading. Then create or update the month index, year index, and `activity-log/index.md` as needed.
3. Append a new section using the format in `templates/activity-entry.md`.
4. Cross-link from the entry to any insight notes touched — a day file sits three levels deep, so climb out: `[<topic>](../../../technical/<topic>.md)`, `[<project>](../../../projects/<project>.md)`. Add the reverse backlink from those notes to this entry's path under `## Backlinks` if the link is durable (not for trivial mentions). Use markdown links, never `[[wikilinks]]`.

## Maintenance

- Every directory needs `index.md` linking to all files in it (except date-leaf directories under `activity-log/`).
- When refactoring (rename, split, delete): update all backlinks that reference the old path. Run `tools/journal-lint.py` after.
- Merge tiny stubs; split files that grow beyond ~80 lines.
- Verify no orphans after structural changes.
