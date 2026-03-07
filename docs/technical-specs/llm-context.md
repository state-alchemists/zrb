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

Only the `index.md` file content is automatically injected into the LLM's system prompt.

```markdown
### Journal & Notes
[Content from index.md]

### Journal System
**Journal System Configuration:**
- **Journal Directory:** `~/.zrb/llm-notes/`
- **Index File:** `index.md`

**Documentation Guidelines:**
- Technical information → `AGENTS.md`
- User preferences, notes → Journal directory
```

---

## 4. Automatic Creation

The journal system automatically creates the directory and index file if they don't exist:

```python
effective_journal_dir = os.path.abspath(os.path.expanduser(CFG.LLM_JOURNAL_DIR))
if not os.path.isdir(effective_journal_dir):
    os.makedirs(effective_journal_dir, exist_ok=True)
    
index_path = os.path.join(effective_journal_dir, CFG.LLM_JOURNAL_INDEX_FILE)
if not os.path.isfile(index_path):
    with open(index_path, "w") as f:
        f.write("")  # Create empty index file
```

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