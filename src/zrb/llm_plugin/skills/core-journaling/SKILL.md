---
name: core-journaling
description: Manage the LLM journal system as a knowledge graph.
user-invocable: false
---
# Skill: core-journaling

## Core Philosophy
The Journal is your **External Long-Term Memory** — a graph-based knowledge base where every file is accessible from `index.md`.

## The Index File (`index.md`)
**ROLE:** Heads-Up Display loaded by default. Contains critical info for immediate task execution.

**Content:**
- Critical user preferences
- Active constraints & protocols
- Recent technical insights (last 5)
- Links to directory indexes

## Graph Structure Rules
1. **RHIZOMATIC LINKING:** Link liberally between related concepts
2. **NO ORPHANS:** Every file MUST be reachable from `index.md`
3. **ATOMICITY:** One concept per file; split if too large

## Directory Structure
```
~/.zrb/llm-notes/
├── index.md           # Heads-Up Display
├── user/index.md
├── preferences/index.md
├── projects/index.md
├── technical/index.md
└── activity-log/      # YYYY/YYYY-MM/YYYY-MM-DD/
```

Create directories as needed. Each MUST have an `index.md`.

## Index Hierarchy
1. Outer `index.md` → directory indexes only
2. Directory indexes → all files in directory
3. Individual files → detailed documentation

## Protocol

### When to Journal
Journal at **task completion** if non-trivial learning occurred (see `journal_mandate.md`).

### Creating Content
- User preferences → outer `index.md` (critical) or directories (detailed)
- Project facts → `projects/`
- Technical insights → `technical/`
- Activity logs → `activity-log/YYYY/YYYY-MM/DD/`

### Maintenance
- Every directory needs `index.md` linking to all files
- Cross-link related concepts
- Refactor if files grow large
- Verify no orphans