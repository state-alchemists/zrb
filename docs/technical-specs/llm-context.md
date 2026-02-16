🔖 [Home](../../README.md) > [Documentation](../README.md)

# LLM Journal System (Technical Specification)

Zrb provides a directory-based journal system for maintaining persistent context across LLM sessions. This allows the assistant to remember project-specific details, user preferences, and local environment information through a hierarchical file system structure.

## 1. Overview

The journal system replaces the old JSON-based note system with a more flexible directory-based approach. It provides a structured way to maintain context through Markdown files organized hierarchically by topic or project.

## 2. Storage Mechanism

Journal entries are stored in a directory structure with a central index file.

-   **Journal Directory**: Defined by the `ZRB_LLM_JOURNAL_DIR` environment variable.
-   **Default Path**: `~/.zrb/llm-notes/`
-   **Index File**: Defined by the `ZRB_LLM_JOURNAL_INDEX_FILE` environment variable.
-   **Default Index**: `index.md`
-   **Structure**: Hierarchical directory structure with Markdown files

### Directory Organization
Users can organize journal entries hierarchically by topic or project:
```
~/.zrb/llm-notes/
├── index.md                    # Main index file (auto-injected into prompts)
├── project-a/
│   ├── design.md              # Design decisions for project A
│   ├── meeting-notes.md       # Meeting notes for project A
│   └── api-spec.md           # API specifications for project A
├── project-b/
│   ├── requirements.md        # Requirements for project B
│   └── architecture.md       # Architecture decisions for project B
└── user-preferences.md       # Global user preferences
```

### Index File Structure
The `index.md` file should be concise and reference other files:
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

## 3. Prompt Injection

Only the `index.md` file content is automatically injected into the LLM's system prompt via placeholder replacement (e.g., `{CFG_LLM_JOURNAL_DIR}`). The system also includes journal configuration information:

```markdown
### Journal & Notes
[Content from index.md]

### Journal System
**Journal System Configuration:**
- **Journal Directory:** `~/.zrb/llm-notes/`
- **Index File:** `index.md`

**Documentation Guidelines:**
- Technical information about project architecture, conventions, and patterns should be maintained in `AGENTS.md`
- User preferences, non-technical context, and session notes can be added to the journal directory
- At the end of significant interactions, consider updating relevant documentation
```

## 4. Automatic Creation

The journal system automatically creates the journal directory and index file if they don't exist:

```python
# Journal prompt component creates directory/file if missing
effective_journal_dir = os.path.abspath(os.path.expanduser(CFG.LLM_JOURNAL_DIR))
if not os.path.isdir(effective_journal_dir):
    os.makedirs(effective_journal_dir, exist_ok=True)
index_path = os.path.join(effective_journal_dir, CFG.LLM_JOURNAL_INDEX_FILE)
if not os.path.isfile(index_path):
    with open(index_path, "w") as f:
        f.write("")  # Create empty index file
```

## 5. Configuration Placeholders

The journal system uses configuration placeholders that are automatically replaced in prompts:

- `{CFG_LLM_JOURNAL_DIR}`: Journal directory path
- `{CFG_LLM_JOURNAL_INDEX_FILE}`: Index filename
- `{CFG_ROOT_GROUP_NAME}`: Root group name (e.g., "zrb")
- `{CFG_LLM_ASSISTANT_NAME}`: Assistant name
- `{CFG_ENV_PREFIX}`: Environment variable prefix

## 6. Documentation Separation

- **AGENTS.md**: For technical documentation only (project architecture, conventions, patterns)
- **Journal**: For non-technical notes, reflections, and project context

## 7. Migration from Old Note System

The old JSON-based note system (`NoteManager`, `LLM_NOTE_FILE`) has been completely removed in version 2.4.0. Users should migrate their notes to the new directory-based journal system by:

1. Creating the journal directory: `mkdir -p ~/.zrb/llm-notes/`
2. Creating an `index.md` file with references to their notes
3. Organizing notes into appropriate subdirectories and Markdown files

## 8. Management

Journal entries are managed directly through the file system. Users can:
- Create/edit Markdown files in the journal directory
- Update the `index.md` file to reference new entries
- Organize entries hierarchically by project or topic

The LLM can reference journal content in its responses and suggest updates to the journal based on significant interactions.
