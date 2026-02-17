# Prompt Engineering System Refactor Plan

## 1. Objective

The goal of this refactor is to improve the efficiency, clarity, and maintainability of the dynamic system prompt. We will achieve this by enhancing how context is injected, removing redundancy, and ensuring all instructional text is externalized and user-configurable.

## 2. Analysis of the Current System

### 2.1. Strengths

*   **Modularity:** The separation of prompts into components like `persona`, `mandate`, and `system_context` is effective.
*   **Dynamic Injection:** The system's ability to inject real-time data (Git status, OS info) is powerful.
*   **Hierarchical Configuration:** The override system (project-specific files > defaults) allows for excellent customization.
*   **Efficient Skill Loading:** The distinction between "active" and "available" skills smartly manages token usage.

### 2.2. Areas for Improvement

*   **Instructional Redundancy:** Core operational rules, especially for Git usage, are defined in multiple places (hardcoded in `system_context.py` and generalized in `mandate.md`), leading to potential conflicts and difficult maintenance.
*   **Token Inefficiency / Prompt Dilution:**
    *   The system prompt includes low-signal information, such as lock files (`poetry.lock`) and negative information (`Docker: Not installed`).
    *   Large documentation files (`AGENTS.md`) are either fully injected or not at all, lacking a middle ground that could provide a summary without consuming excessive tokens.
*   **Inconsistent Configuration:** Most instructional prompts are loaded from `.md` files, but some critical mandates (e.g., Git rules) are hardcoded within Python source code, breaking the established customization pattern.

## 3. Actionable Refactoring Plan

The following steps should be executed to address the issues identified above.

### 3.1. Externalize Git Mandates to `git_mandate.md`

*   **Task:** Move the hardcoded Git operational rules out of `src/zrb/llm/prompt/system_context.py`.
*   **Implementation:**
    1.  Create a new file: `src/zrb/llm/prompt/markdown/git_mandate.md`.
    2.  Populate this file with the rules currently found in the `_get_git_info` function (e.g., "You MUST NEVER stage or commit changes...").
    3.  Modify the `_get_git_info` function in `system_context.py`. It should now report only the state (Branch, Status). The mandates should be loaded and injected separately by having the `PromptManager` pipeline use `get_default_prompt("git_mandate")`. This ensures the rules are sourced from the markdown file and can be overridden by users.

### 3.2. Implement Header-Based Summarization for Documentation

*   **Task:** Change the injection logic for `CLAUDE.md` and `AGENTS.md` in `src/zrb/llm/prompt/claude.py`.
*   **Implementation:**
    1.  Instead of injecting the full file content based on a simple character count, implement a markdown-aware parser.
    2.  This parser should extract all markdown headers (`#`, `##`, etc.) and the first ~150-250 characters of the content immediately following each header.
    3.  The final injected text should be a structured summary that functions as an "actionable table of contents," prefixed with a clear instruction for the AI, like: *"The following is a summary of `AGENTS.md`. Use the 'Read' tool to get the full content of the file or a specific section when needed."*
    4.  The total length of this summary should still be capped (e.g., 20k characters) to prevent excessive token usage.

### 3.3. Implement Semantic File Categorization

*   **Task:** Refactor the `_get_project_files` function in `src/zrb/llm/prompt/system_context.py`.
*   **Implementation:**
    1.  Modify the function to group the detected high-signal files by their corresponding technology or purpose.
    2.  Instead of a flat comma-separated string, the output should be a structured, human-readable list.
    3.  **Example Output:**
        ```markdown
        - **Project Files (Detected):**
          - **Python:** pyproject.toml, zrb_init.py
          - **JavaScript/Node.js:** package.json
          - **Containerization:** Dockerfile, .dockerignore
        ```

### 3.4. Optimize Runtime Tool Information

*   **Task:** Clean up the output of the `_get_runtime_info` function in `src/zrb/llm/prompt/system_context.py`.
*   **Implementation:**
    1.  Modify the logic to only include entries for tools that are successfully found on the system.
    2.  Completely omit any lines for tools that are "Not installed".

## 4. Desired Outcome

The refactored system prompt will be more concise, contextually intelligent, and easier to maintain. An assistant reading the prompt will receive a clearer, more focused set of instructions and context, free of redundant rules and low-signal noise, enabling better performance on downstream tasks.
