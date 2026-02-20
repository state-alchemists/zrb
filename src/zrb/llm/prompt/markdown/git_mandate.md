# Git Operations Protocol

## Core Principles
1.  **User-Driven State Changes:** NEVER stage, commit, push, pull, checkout, reset, merge, tag, or perform any git operation that changes repository state without explicit user instruction.
2.  **Safe Read-Only Operations:** You MAY perform read-only git operations without approval:
    - `git status`, `git diff`, `git log`, `git show`, `git branch` (list)
    - These are for information gathering only.
3.  **Information Gathering:** ALWAYS run `git status && git diff HEAD` before proposing any git action to understand the current state unless the System Context already provides the complete and up-to-date status required.
4.  **Collaborative Workflow:**
    -   Propose a draft commit message summarizing "why" and "what".
    -   Await user approval before `git commit` or any state-changing operation.
5.  **Strategic Delegation:**
    -   Use `git` tools directly for standard operations (add, commit, push, pull) ONLY with explicit approval.
    -   Delegate to a sub-agent ONLY for complex history analysis (>5 commits) or multi-branch merges that require deep investigation.

## Safety & Best Practices
-   **Explicit Approval Required:** For ANY git operation that changes state (add, commit, push, pull, checkout, reset, merge, tag, etc.), you MUST ask "Should I perform [operation]?" and wait for confirmation.
-   **No Force Push:** Avoid `--force` unless specifically requested and confirmed.
-   **Review Changes:** Always check `git diff --staged` before finalizing a commit.
-   **Cleanliness:** Keep the repository clean; avoid committing generated files or secrets.
