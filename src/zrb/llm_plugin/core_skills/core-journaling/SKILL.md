---
name: core-journaling
description: "Activate before *structural* journal work — creating a directory, restructuring or repairing indexes, renaming/splitting/deleting notes, running journal-lint, or reconciling a legacy journal. Everyday writes (one activity line, one insight note) are covered by the Journal Protocol and need no activation. Provides the graph protocol (bidirectional links, indexes), the directory layout, and the long-form activity entry."
user-invocable: false
---
# Skill: core-journaling

The Journal is a bidirectional graph knowledge base plus a chronological log book. Every note links to related notes; every link has a reverse (backlink). The root `index.md` is your Heads-Up Display. The `activity-log/` subtree records what was done over time.

**When to use this skill.** The Journal Protocol in the system prompt carries the everyday write shapes — one activity line, one insight note — and those do not require activating this skill. Activate it for **structural** work: creating a directory, restructuring or repairing indexes, renaming/splitting/deleting notes, running `journal-lint.py`, reconciling a legacy journal, or any entry the Protocol's two shapes do not cover.

**The graph protocol below governs every write regardless.** A forward link without its reverse is how the journal becomes a half-graph: some notes linked, others orphaned. The everyday shapes are a *subset* of this protocol, not an exemption from it — when in doubt about layout or linking, activate and follow this file.

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

## Legacy Journals (predating this layout)

An existing journal may not match the structure above — earlier conventions used `[[wikilinks]]`, a flat `user.md` instead of `user/`, no `preferences/` directory, or a different `activity-log/` nesting. Several layouts can coexist in one tree.

**A non-conforming journal is valid to read and valid to append to. Do not migrate it as a side effect of an unrelated write.**

- **Reading:** search and read it as-is. Old entries are evidence regardless of their shape.
- **Appending to a file that already exists:** append and stop. Adding a line to an existing file changes nothing about reachability, so it triggers no index work — even if that file is itself unindexed or sits under an older nesting. Prefer the file that is already there over a correctly-named rival: one timeline beats a tidy one.
- **Creating a file:** use the layout above, and index it. The graph invariants (no orphans, every directory has an `index.md`) bind the files *you create* — they are not a standing obligation to repair what you found.
- **Repairing:** restructuring, re-pathing links, or consolidating duplicate trees is its own task. Propose it, get approval, then do it in one pass with `tools/journal-lint.py` verifying the result. Never fold it into another turn's work.
- **Root index:** if the HUD is hand-shaped (custom headings, inlined preferences), keep its shape and add to it. The index is the user's dashboard, not a generated file.

## Maintenance

- Every directory needs `index.md` linking to all files in it (except date-leaf directories under `activity-log/`).
- When refactoring (rename, split, delete): update all backlinks that reference the old path. Run `tools/journal-lint.py` after.
- Merge tiny stubs; split files that grow beyond ~80 lines.
- Verify no orphans after structural changes.
