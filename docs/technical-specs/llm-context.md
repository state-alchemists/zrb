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
| Journal Directory | `ZRB_LLM_JOURNAL_DIR` | `~/.zrb/llm-notes/` |
| Index File | `ZRB_LLM_JOURNAL_INDEX_FILE` | `index.md` |

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
[content of index.md, truncated to ~1000 characters, with " (...more)" appended if truncated]
</journal-index>
```

If the index file is missing, unreadable, or empty, nothing is injected at all.

---

## 4. Automatic Creation

Zrb does **not** auto-create the journal directory or the index file. There is no code path under `src/zrb/llm/` that calls `os.makedirs` or otherwise materializes `~/.zrb/llm-notes/` or `index.md` on startup — `src/zrb/llm/tool/journal.py` only implements a `search_journal` tool (exposed to the agent as `SearchJournal`) for reading existing entries.

Creating the directory, the index file, and any per-topic Markdown files is the agent's own responsibility, driven entirely by prompt/skill guidance (see the `core-journaling` skill under `src/zrb/llm_plugin/core_skills/`) rather than by zrb's runtime code. If the agent never decides to journal, the directory and index simply never come into existence.

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