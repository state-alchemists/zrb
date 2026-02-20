# Git Operations Protocol

## Core Principles
1.  **User-Driven Commits:** NEVER stage or commit changes without explicit user instruction.
2.  **Information Gathering:** ALWAYS run `git status && git diff HEAD` before proposing any git action to understand the current state.
3.  **Collaborative Workflow:**
    -   Propose a draft commit message summarizing "why" and "what".
    -   Await user approval before `git commit`.
4.  **Strategic Delegation:**
    -   Use `git` tools directly for standard operations (add, commit, push, pull).
    -   Delegate to a sub-agent ONLY for complex history analysis (>5 commits) or multi-branch merges that require deep investigation.

## Safety & Best Practices
-   **No Force Push:** Avoid `--force` unless specifically requested and confirmed.
-   **Review Changes:** Always check `git diff --staged` before finalizing a commit.
-   **Cleanliness:** Keep the repository clean; avoid committing generated files or secrets.
