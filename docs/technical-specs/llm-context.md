# LLM Context and Workflow Requirements

This document outlines the requirements for managing LLM context and workflows using a special configuration file. The goal is to allow users to define context-sensitive instructions and standard operating procedures (SOPs) for the LLM based on their current working directory.

## 1. Overview

The system uses a special file to define "Workflows" and "Contexts".

-   **Workflow**: A named set of instructions or an SOP for the LLM for a specific task (e.g., "coding", "testing", "docs").
-   **Context**: Notes or information associated with a specific directory.

The system searches for this file starting from the current working directory and traversing upwards to the user's home directory. This allows for global, project-level, and directory-level configurations, with closer (more specific) configurations taking precedence.

The name of this file is defined by the configuration setting `CFG.LLM_CONTEXT_FILE`, which defaults to `ZRB.md`.

## 2. File Format

The context file uses a simple, flat Markdown structure. Each top-level H1 header (`#`) acts as a key. The content following a header, up to the next H1 header, is its value.

There are two valid key formats:

-   `# Workflow: <workflow_name>`
-   `# Context: <directory_path>`

Any other H1 headers will be ignored.

### Example File: `ZRB.md`

```markdown
# Workflow: coding
- Use Python for all new scripts.
- Adhere strictly to the PEP8 style guide.
- Include docstrings for all functions.

# Context: .
This is the root directory of our main project.
It contains the primary configuration and source code.

# Context: ~/common-libs
This directory contains shared libraries. Do not modify files here
without consulting the core team.

# Ignored Header
This content will be ignored by the parser.
```

## 3. Resolution Logic (Reading)

When the LLM is invoked, it resolves workflows and contexts by searching for the `ZRB.md` file. The search starts in the current directory and proceeds up the directory tree to the user's home directory (`~/`).

### Workflow Resolution

-   The system searches for a `# Workflow: <name>` entry.
-   The **first one found** during the upward search is used. Any workflows with the same name in parent directories are ignored. This "closest wins" approach ensures the most specific workflow is applied.

#### Example:

Suppose we have the following directory structure and files:

-   `/home/user/ZRB.md`:
    ```markdown
    # Workflow: coding
    - Global default: Use Python.
    ```
-   `/home/user/project/ZRB.md`:
    ```markdown
    # Workflow: coding
    - Project-specific: Use TypeScript.
    ```

| Current Directory         | Resolved `coding` Workflow         |
| ------------------------- | ---------------------------------- |
| `/home/user/project/src`  | `- Project-specific: Use TypeScript.` |
| `/home/user/project`      | `- Project-specific: Use TypeScript.` |
| `/home/user`              | `- Global default: Use Python.`    |

### Context Resolution

-   The system gathers all `# Context: <path>` entries from all `ZRB.md` files found during the upward search.
-   A context is considered "relevant" if its `<directory_path>` is an ancestor of, or the same as, the current working directory.
-   If multiple contexts are defined for the **exact same path**, the one from the file closest to the current directory takes precedence.

#### Path Normalization:

-   If `<directory_path>` is absolute (e.g., `/home/user/project`), it is used as is.
-   If `<directory_path>` is relative (e.g., `.` or `src`), it is resolved relative to the directory containing the `ZRB.md` file.

#### Example:

-   `/home/user/ZRB.md`:
    ```markdown
    # Context: /home/user/project
    This is the main project folder (from home).
    ```
-   `/home/user/project/ZRB.md`:
    ```markdown
    # Context: .
    This is the project source (from project root).
    ```
-   `/home/user/project/src/ZRB.md`:
    ```markdown
    # Context: .
    This is the 'src' directory.
    ```

If the current directory is `/home/user/project/src`, the system would retrieve the following contexts:

1.  **From `/home/user/project/src/ZRB.md`**: The context for `.` (resolved to `/home/user/project/src`).
2.  **From `/home/user/project/ZRB.md`**: The context for `.` (resolved to `/home/user/project`).
3.  **From `/home/user/ZRB.md`**: The context for `/home/user/project`.

The final, aggregated context would include the notes for `/home/user/project/src` and `/home/user/project`.

## 4. Writing Logic

When adding or updating a context entry, the system will always write to the `ZRB.md` file in the **current working directory**. If the file does not exist, it should be created.

The `<directory_path>` written to the file follows these rules to ensure portability and clarity:

1.  **Path inside Current Directory**: If the target path is within the current working directory, it is written as a **relative path**.
    -   *Example*: CWD is `/home/user/project`. Adding context for `/home/user/project/src`. The file entry is `# Context: src`.

2.  **Path inside Home Directory**: If the target path is outside the current directory but within the user's home directory, it is written relative to home, using the `~` character.
    -   *Example*: CWD is `/home/user/project`. Adding context for `/home/user/other-project`. The file entry is `# Context: ~/other-project`.

3.  **Absolute Path**: For any other path (e.g., a system directory), the **absolute path** is used.
    -   *Example*: CWD is `/home/user/project`. Adding context for `/etc/nginx`. The file entry is `# Context: /etc/nginx`.

### Example:

| Current Directory (CWD) | Path to Add             | Resulting Entry in `./ZRB.md` |
| ----------------------- | ----------------------- | ---------------------------------- |
| `/home/user/project`    | `/home/user/project/lib`| `# Context: lib`                   |
| `/home/user/project`    | `/home/user/docs`       | `# Context: ~/docs`                |
| `/home/user/project`    | `/var/log`              | `# Context: /var/log`              |