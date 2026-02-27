# Git Operations Protocol

## Core Principles
1.  **User-Driven State Changes:** NEVER stage, commit, push, pull, checkout, reset, merge, tag without explicit user instruction.
2.  **Safe Read-Only Operations:** MAY perform read-only: `git status`, `git diff`, `git log`, `git show`, `git branch` (list). Information gathering only.
3.  **Information Gathering:** ALWAYS run `git status && git diff HEAD` before proposing git action unless System Context provides complete status.
4.  **Collaborative Workflow:** Propose draft commit message ("why"/"what"). Await user approval before `git commit` or any state-changing operation.
5.  **Strategic Delegation:** Use `git` tools directly ONLY with explicit approval. Delegate to sub-agent ONLY for complex history analysis (>5 commits) or multi-branch merges.

## Safety & Best Practices
-   **Explicit Approval Required:** For ANY state-changing git operation, MUST ask "Should I perform [operation]?" and wait confirmation.
-   **No Force Push:** Avoid `--force` unless specifically requested/confirmed.
-   **Review Changes:** Always check `git diff --staged` before finalizing commit.
-   **Cleanliness:** Keep repository clean; avoid committing generated files/secrets.
