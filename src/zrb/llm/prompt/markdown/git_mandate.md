# Git Rules

---

## State-Changing Commands: Require Explicit Approval

Always get explicit user approval before running any of these commands.

| Command | Why Approval Required |
|---------|----------------------|
| `git add` | Stages changes to the index, preparing them for commit. Accidental staging can lead to unintended commits. |
| `git commit` | Creates a permanent snapshot in the repository history. Cannot be easily undone in shared repositories. |
| `git push` | Publishes local commits to a remote repository, making them visible to all collaborators. |
| `git pull` | Fetches and merges remote changes into the local branch, potentially causing merge conflicts or overwriting local changes. |
| `git merge` | Combines branches, creating merge commits that alter repository history. |
| `git rebase` | Rewrites commit history by moving or combining commits. Can cause irrecoverable data loss if misused. |
| `git checkout` | Switches branches or restores files, potentially discarding uncommitted changes. |
| `git switch` | Switches branches (modern alternative to checkout), may trigger merge conflicts or stash operations. |
| `git branch -D` | Forcefully deletes a branch, potentially losing unmerged work permanently. |
| `git reset` | Moves the HEAD pointer, potentially discarding commits or staged changes depending on flags used. |
| `git revert` | Creates a new commit that undoes a previous commit. Changes history indirectly and may affect collaborators. |
| `git stash` | Temporarily shelves changes. If forgotten, work may be lost or difficult to recover. |
| `git tag` | Creates permanent reference points in history. Tag management affects release workflows. |
| `git clean` | Removes untracked files and directories. **Irreversible** — deleted files cannot be recovered. |

**CRITICAL**: Never execute state-changing commands without explicit user approval.

---

## Read-Only Commands: Always OK

These commands can be safely executed at any time.

| Command | Why It's Safe |
|---------|---------------|
| `git status` | Only displays the current state of the working directory and index. No modifications. |
| `git diff` | Shows differences between commits, branches, or files. Read-only comparison. |
| `git log` | Displays commit history. Purely informational. |
| `git branch` | Lists branches without modification (when used without flags). Safe inspection. |
| `git show` | Displays commit contents, file changes, or tag information. Read-only. |
| `git remote -v` | Lists configured remote repositories. Purely informational. |

---

## How to Ask

1. Run `git status` and `git diff HEAD` to show current state
2. Propose the exact command: "Should I run `git <command> <args>`?"
3. Wait for "Yes" before proceeding