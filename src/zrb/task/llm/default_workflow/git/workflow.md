---
description: "A workflow for managing version control with git."
---
# Git Workflow Guide

This guide governs all version control operations. Adhere to it for safety and consistency.

## 1. Core Principles & Safety

- **Atomic Commits:** One logical change per commit. Use `git add -p` for precision.
- **Descriptive Messages:** Explain the "why" in the imperative mood (e.g., "Add feature"). Follow the 50/72 format.
- **Safety First:**
  - Always run `git status` before operations.
  - Use `git push --force-with-lease`, not `--force`.
  - Ensure the working directory is clean before `git rebase`.

## 2. Standard Workflow

This is the primary development cycle.

1. **Branch:** `git checkout -b <branch-name>`
2. **Code & Verify:** Make changes, then run all tests, linters, and builds.
3. **Stage:** `git add <file>` or, for more precision, `git add -p`.
4. **Commit:** `git commit` with a descriptive message.
    ```
    feat: Add user authentication endpoint

    Implement the /login endpoint using JWT for token-based auth.
    This resolves issue #123 by providing a mechanism for users to
    log in and receive an access token.
    ```
5. **Review/Amend:** Use `git log -1` to review. If needed, fix with `git commit --amend`.
6. **Push:** `git push origin <branch-name>`

## 3. Command Reference

### Status & History
- `git status`: Check working directory status.
- `git diff`: See uncommitted changes to tracked files.
- `git diff --staged`: See staged changes.
- `git log --oneline --graph -10`: View recent commit history.
- `git blame <file>`: See who changed what in a file.

### Branching & Merging
- `git checkout -b <name>`: Create and switch to a new branch.
- `git switch <name>`: Switch to an existing branch.
- `git rebase main`: Update the current branch from `main`. **(Use with care)**.
- `git merge --no-ff <branch>`: Merge a branch without fast-forwarding.

### Stashing
- `git stash push -m "msg"`: Save uncommitted changes temporarily.
- `git stash list`: List all stashes.
- `git stash pop`: Apply and remove the last stash.

### Remote Operations
- `git fetch origin`: Fetch updates from the remote repository.
- `git push origin <branch>`: Push a branch to the remote.
- `git push origin --delete <branch>`: Delete a remote branch.

### Advanced
- `git cherry-pick <commit-hash>`: Apply a specific commit from another branch. **(Use with caution to avoid duplicate commits)**.
