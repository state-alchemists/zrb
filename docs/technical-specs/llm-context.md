🔖 [Documentation Home](../../README.md) > [Technical Specs](./llm-context.md)

# LLM Journal System (Technical Specification)

Zrb provides a directory-based journal system for maintaining persistent context across LLM sessions. This allows the assistant to remember project-specific details, user preferences, and local environment information through a hierarchical file system structure.

---

## Table of Contents

- [Overview](#1-overview)
- [Storage Mechanism](#2-storage-mechanism)
- [Prompt Injection](#3-prompt-injection)
- [Automatic Creation](#4-automatic-creation)
- [Configuration Placeholders](#5-configuration-placeholders)
- [Documentation Separation](#6-documentation-separation)
- [Migration Guide](#7-migration-from-old-note-system)

---

## 1. Overview

The journal system replaces the old JSON-based note system with a more flexible directory-based approach. It provides a structured way to maintain context through Markdown files organized hierarchically by topic or project.

| Feature | Old System | New System |
|---------|------------|------------|
| Storage | Single JSON file | Directory of Markdown files |
| Organization | Flat | Hierarchical |
| Format | JSON | Markdown |
| Index | N/A | `index.md` |

---

## 2. Storage Mechanism

Journal entries are stored in a directory structure with a central index file.

| Setting | Environment Variable | Default |
|---------|---------------------|---------|
| Enabled | `ZRB_LLM_JOURNAL_ENABLED` | `on` |
| Journal Directory | `ZRB_LLM_JOURNAL_DIR` | `~/.zrb/llm-notes/` |
| Index File | `ZRB_LLM_JOURNAL_INDEX_FILE` | `index.md` |
| Injected index cap | `ZRB_LLM_JOURNAL_INDEX_MAX_CHARS` | `2500` |

`ZRB_LLM_JOURNAL_ENABLED=false` turns the whole subsystem off — the Journal
Protocol prompt section, the `<journal-index>` injection, the `SearchJournal`
tool, and the built-in `core-journaling` skill all disappear together, so the
model is never told a journal exists. The gate lives in
`PromptManager.active_sections`, which drops `journal_mandate`; the index
injection and both summarization paths already key on that section's presence,
so one filter reaches all of them (ADR-0097).

`ZRB_LLM_JOURNAL_DIR` is **not** an off switch: clearing it falls back to
`~/.zrb/llm-notes/` rather than disabling journaling.

### Directory Organization

```
~/.zrb/llm-notes/
├── index.md                    # Main index (auto-injected)
├── project-a/
│   ├── design.md              # Design decisions
│   ├── meeting-notes.md       # Meeting notes
│   └── api-spec.md            # API specs
├── project-b/
│   ├── requirements.md        # Requirements
│   └── architecture.md        # Architecture
└── user-preferences.md        # Global preferences
```

### Index File Structure

```markdown
# Journal Index

## Project A
- [Design Decisions](project-a/design.md)
- [Meeting Notes](project-a/meeting-notes.md)
- [API Specifications](project-a/api-spec.md)

## Project B  
- [Requirements](project-b/requirements.md)
- [Architecture](project-b/architecture.md)

## Global Preferences
- [User Preferences](user-preferences.md)
```

---

## 3. Prompt Injection

The `index.md` snapshot is deliberately kept **out of** the cached system prompt (`src/zrb/llm/prompt/live_context.py::render_journal_index`). Embedding the mutable index in the cached prefix would invalidate that cache every time the agent journaled mid-session (ADR-0082), so instead it travels through the conversation itself, as part of the `<live-context>` block appended to the latest **user** message — never the system prompt.

The index is only injected at the two moments it could otherwise be missing from context:

- **The first turn** — when history is still empty, `render_live_context(..., inject_journal_index=True)` appends the snapshot.
- **History summarization** — `summarize_history` re-seeds the index into the freshly-compressed history so it survives compaction.

On every other turn, the block is simply omitted — the agent is expected to already have it from earlier in the conversation.

When present, the block is wrapped as its own tag inside the live-context payload:

```
<journal-index>
Your persistent memory (index file: index.md). Use SearchJournal for full entries.
[content of index.md, capped at ZRB_LLM_JOURNAL_INDEX_MAX_CHARS]
</journal-index>
```

When the content exceeds the cap it is cut **on a line boundary** and ` (...more)`
is appended, and the header gains a pointer to the rest:

```
Your persistent memory (index file: index.md). Truncated at `(...more)`; Read /abs/path/to/index.md for the rest. Use SearchJournal for full entries.
```

Cutting on a line boundary matters because the entries are facts about the user —
half a sentence is worse than none. Overflow is dropped from the **end**, so the
index should be written most-durable-first (the `core-journaling` skill's HUD
template fixes that order: identity and standing preferences first, unbounded
"recent insights" last, so growth only ever evicts itself).

Nothing is injected at all when the index file is missing, unreadable, or empty;
when `ZRB_LLM_JOURNAL_INDEX_MAX_CHARS` is `0`; or when
`ZRB_LLM_JOURNAL_ENABLED` is `false`. Because a missing block therefore does not
prove an empty journal, the Journal Protocol tells the model to `SearchJournal`
before concluding one way or the other.

---

## 4. Automatic Creation

Zrb creates the journal **directory** on first search, and nothing else. `search_journal` (`src/zrb/llm/tool/journal.py`, exposed to the agent as `SearchJournal`) calls `os.makedirs(..., exist_ok=True)` when the configured directory is absent and reports the same empty result an unmatched search returns.

That behaviour is deliberate. Reporting a missing directory as an error made the whole memory layer read as unavailable, and the agent responded by declaring it could not journal rather than by writing its first note — the directory could not come into existence because nothing would create it. An unwritten journal is *empty*, not broken.

The index file and every per-topic Markdown file remain the agent's responsibility, driven by prompt and skill guidance (see the `core-journaling` skill under `src/zrb/llm_plugin/core_skills/`) rather than by zrb's runtime code.

---

## 5. Configuration Placeholders

The journal system uses configuration placeholders that are automatically replaced in prompts:

| Placeholder | Replaced With |
|-------------|---------------|
| `{CFG_LLM_JOURNAL_DIR}` | Journal directory path |
| `{CFG_LLM_JOURNAL_INDEX_FILE}` | Index filename |
| `{CFG_ROOT_GROUP_NAME}` | Root group name (e.g., "zrb") |
| `{CFG_LLM_ASSISTANT_NAME}` | Assistant name |
| `{CFG_ENV_PREFIX}` | Environment variable prefix |

---

## 6. Documentation Separation

| Location | Content Type |
|----------|-------------|
| `AGENTS.md` | Technical documentation (architecture, conventions, patterns) |
| Journal | Non-technical notes, reflections, project context |

> 💡 **Best Practice:** Use `AGENTS.md` for rules the LLM must follow. Use the journal for information the LLM should remember.

---

## 7. Migration from Old Note System

The old JSON-based note system (`NoteManager`, `LLM_NOTE_FILE`) was removed in version 2.4.0.

### Migration Steps

```bash
# 1. Create journal directory
mkdir -p ~/.zrb/llm-notes/

# 2. Create index file
touch ~/.zrb/llm-notes/index.md

# 3. Organize notes into Markdown files
# Move content from old JSON to categorized .md files
```

| Old System | New System |
|------------|------------|
| Single JSON file | Directory structure |
| `NoteManager` class | Direct file access |
| `LLM_NOTE_FILE` env var | `ZRB_LLM_JOURNAL_DIR` |

---