---
description: "A workflow for managing version control with git."
---
Follow this workflow for safe, consistent, and effective version control operations.

# Core Mandates

- **Safety First:** Never force operations that could lose data
- **Atomic Commits:** One logical change per commit
- **Descriptive Messages:** Explain the "why" in imperative mood
- **Clean History:** Maintain a readable and useful commit history

# Tool Usage Guideline
- Use `run_shell_command` for all git operations
- Use `read_from_file` to examine git configuration files
- Use `search_files` to find specific commit messages or patterns

# Step 1: Pre-Operation Safety Check

1. **Check Status:** Always run `git status` before operations
2. **Verify Working Directory:** Ensure the working directory is clean before destructive operations
3. **Review Changes:** Use `git diff` and `git diff --staged` to understand what will be committed
4. **Backup Important Changes:** Consider stashing or creating a backup branch for risky operations

# Step 2: Standard Development Workflow

1. **Create Feature Branch:** `git checkout -b <branch-name>`
2. **Make Changes:** Implement features or fixes
3. **Stage Changes:** Use `git add -p` for precision staging
4. **Commit with Description:** Write clear, descriptive commit messages
5. **Review and Amend:** Use `git log -1` to review, amend if needed
6. **Push to Remote:** `git push origin <branch-name>`

# Step 3: Commit Message Standards

```
feat: Add user authentication endpoint

Implement the /login endpoint using JWT for token-based auth.
This resolves issue #123 by providing a mechanism for users to
log in and receive an access token.
```

- **Type Prefix:** feat, fix, docs, style, refactor, test, chore
- **Imperative Mood:** "Add feature" not "Added feature"
- **50/72 Rule:** 50 character subject, 72 character body lines

# Step 4: Branch Management

## Safe Branch Operations
- **Create:** `git checkout -b <name>` or `git switch -c <name>`
- **Switch:** `git switch <name>`
- **Update:** `git rebase main` (use with care)
- **Merge:** `git merge --no-ff <branch>` for explicit merge commits

## Remote Branch Operations
- **Fetch Updates:** `git fetch origin`
- **Push:** `git push origin <branch>`
- **Delete Remote:** `git push origin --delete <branch>`

# Step 5: Advanced Operations (Use with Caution)

## Rebasing
- **Update Branch:** `git rebase main`
- **Interactive:** `git rebase -i <commit>` for history editing
- **Safety:** Never rebase shared/public branches

## Stashing
- **Save Changes:** `git stash push -m "message"`
- **List Stashes:** `git stash list`
- **Apply:** `git stash pop` or `git stash apply`

## Cherry-picking
- **Apply Specific Commit:** `git cherry-pick <commit-hash>`
- **Use Case:** Only when absolutely necessary to avoid duplicate commits

# Step 6: Verification and Cleanup

1. **Verify Operations:** Check `git status` and `git log` after operations
2. **Run Tests:** Ensure all tests pass after changes
3. **Clean Up:** Remove temporary branches and stashes when no longer needed
4. **Document:** Update documentation if workflow changes affect team processes

# Risk Assessment Guidelines

## Low Risk (Proceed Directly)
- `git status`, `git log`, `git diff`
- Creating new branches
- Stashing changes

## Moderate Risk (Explain and Confirm)
- `git rebase` operations
- `git push --force-with-lease`
- Deleting branches

## High Risk (Refuse and Explain)
- `git push --force` (use --force-with-lease instead)
- Operations that could lose commit history
- Modifying shared/public branches

# Common Commands Reference

## Status & History
- `git status`: Check working directory status
- `git diff`: See uncommitted changes to tracked files
- `git diff --staged`: See staged changes
- `git log --oneline --graph -10`: View recent commit history
- `git blame <file>`: See who changed what in a file

## Branch Operations
- `git branch -a`: List all branches (local and remote)
- `git branch -d <branch>`: Delete a local branch
- `git remote prune origin`: Clean up remote tracking branches

## Configuration
- `git config --list`: View current configuration
- `git config user.name "Your Name"`: Set user name
- `git config user.email "your.email@example.com"`: Set user email