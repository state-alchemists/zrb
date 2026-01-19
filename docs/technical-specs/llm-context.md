🔖 [Home](../../README.md) > [Documentation](../README.md)

# LLM Notes & Context (Technical Specification)

Zrb provides a mechanism for maintaining persistent, location-aware notes and context that are automatically provided to the LLM. This allows the assistant to remember project-specific details, user preferences, and local environment information.

## 1. Overview

The system manages a collection of "Notes" associated with specific directory paths. When an LLM task is executed, it retrieves all notes relevant to the current working directory (including those from parent directories) and injects them into the system prompt.

## 2. Storage Mechanism

Notes are stored in a single, global JSON file.

-   **File Location**: Defined by the `ZRB_LLM_NOTE_FILE` environment variable.
-   **Default Path**: `~/.zrb/notes.json`
-   **Structure**: A simple JSON object where keys are normalized paths and values are strings containing the note content.

### Path Normalization
Paths are normalized to ensure consistency across different environments:
-   Paths inside the user's home directory are stored with a tilde (e.g., `~/projects/zrb`).
-   Paths outside the home directory are stored as absolute paths (e.g., `/etc/nginx`).
-   The user's home directory itself is stored as `~`.

### Example `notes.json`:
```json
{
  "~": "The user prefers Python and likes concise answers.",
  "~/projects/zrb": "This is the Zrb project. It uses Poetry for dependency management.",
  "~/projects/zrb/src": "This directory contains the core library source code."
}
```

## 3. Resolution Logic (Cascading Context)

When an LLM task is executed from a directory (e.g., `/home/user/projects/zrb/src`), the system retrieves notes using a **cascading** approach:

1.  **Identify Ancestors**: The system identifies all ancestor directories of the current path up to the root or home directory.
2.  **Retrieve Notes**: It looks up each ancestor path in the global `notes.json` file.
3.  **Aggregate**: All found notes are collected.

### Example Resolution:
If the current directory is `~/projects/zrb/src`:
-   It checks `~`
-   It checks `~/projects`
-   It checks `~/projects/zrb`
-   It checks `~/projects/zrb/src`

All content found for these keys is aggregated into a single "Notes & Context" block.

## 4. Prompt Injection

The aggregated notes are formatted into a Markdown section and appended to the LLM's system prompt:

```markdown
### Notes & Context
**~**:
The user prefers Python and likes concise answers.

**~/projects/zrb**:
This is the Zrb project. It uses Poetry for dependency management.

**~/projects/zrb/src**:
This directory contains the core library source code.
```

## 5. Management

Notes can be managed programmatically via the `NoteManager` class or by the LLM itself using tools.

### Programmatic Access
```python
from zrb.llm.note.manager import NoteManager

manager = NoteManager()

# Write a note
manager.write("~/my-project", "This project uses FastAPI.")

# Read all relevant notes for a path
notes = manager.read_all("~/my-project/app")
```

### LLM Tools
The `zrb llm chat` command provides the LLM with tools to read and write these notes, allowing it to "remember" facts about the project it is working on.
