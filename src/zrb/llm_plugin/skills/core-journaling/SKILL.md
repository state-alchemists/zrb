---
name: core-journaling
description: Manage the LLM journal system as a knowledge graph.
user-invocable: false
---
# Skill: core-journaling

## Core Philosophy
The Journal is your **External Long-Term Memory** — a bidirectional graph knowledge base where every note links to related notes and every link is tracked in reverse (backlinks). The root `index.md` is your Heads-Up Display.

## Link Convention

Use standard markdown links for all internal references. All paths are **relative to the journal root**:
- `[asyncio patterns](technical/python-asyncio.md)`
- `[projects index](projects/index.md)`

On creation, **always update the target note** with a backlink in its `## Backlinks` section.

### Backlink Protocol

Every note (except `index.md`) **must** have a `## Backlinks` section at the bottom. When you create a link to a target, append the source path to `target.md`'s `## Backlinks` section.

```markdown
## Backlinks
- [projects/my-app](projects/my-app.md) — referenced for auth architecture
- [technical/jwt](technical/jwt.md) — related algorithm
```

**Rules:**
1. Add a backlink immediately when you create a forward link.
2. When deleting a link, remove the corresponding backlink in the target.
3. Keep backlink entries short — path + one-phrase reason.

## The Index File (`index.md`)
**ROLE:** Heads-Up Display loaded by default. Contains critical info for immediate task execution.

**Content:**
- Critical user preferences
- Active constraints & protocols
- Recent technical insights (last 5, each a markdown link)
- Links to directory indexes

## Graph Structure Rules
1. **BIDIRECTIONAL:** Every forward link must have a backlink entry in the target.
2. **NO ORPHANS:** Every file MUST be reachable from `index.md` via forward links.
3. **ATOMICITY:** One concept per file; split if too large.
4. **RHIZOMATIC:** Link liberally between related concepts across directories.

## Directory Structure
```
~/.zrb/llm-notes/
├── index.md                    # Heads-Up Display (links to all directory indexes)
├── user/index.md
├── preferences/index.md
├── projects/index.md
├── technical/index.md
└── activity-log/               # YYYY/YYYY-MM/YYYY-MM-DD/
```

Create directories as needed. Each MUST have an `index.md` that links to every file in that directory.

## Index Hierarchy
1. Outer `index.md` → directory indexes only (e.g. `[projects](projects/index.md)`)
2. Directory indexes → all files in that directory
3. Individual files → detailed documentation with backlinks section

## Protocol

### When to Journal
Journal at **task completion** if non-trivial learning occurred (see `journal_mandate.md`).

### Creating Content
- User preferences → outer `index.md` (critical) or directories (detailed)
- Project facts → `projects/`
- Technical insights → `technical/`
- Activity logs → `activity-log/YYYY/YYYY-MM/DD/`

### Step-by-step for a New Note
1. Write the note content.
2. Add markdown links to related notes throughout the body.
3. Add `## Backlinks` section at bottom (initially empty or pre-populated if you know who will link here).
4. For each link you just added, open the target file and append this note to its `## Backlinks` section.
5. Add a markdown link to the new note from the relevant directory `index.md`.
6. If noteworthy enough for the top-level, add a link from outer `index.md` under *Recent Insights*.

### Maintenance
- Every directory needs `index.md` linking to all files in it.
- When refactoring (rename, split, delete): update all backlinks that reference the old path.
- Verify no orphans after structural changes.
- Merge tiny stubs; split files that grow beyond ~50 lines.
