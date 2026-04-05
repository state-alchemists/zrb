# Git Rules

## State-Changing Commands: Require Explicit Approval

Always get explicit user approval before running:

`git add` · `git commit` · `git push` · `git pull` · `git merge` · `git rebase` · `git checkout` · `git switch` · `git branch -D` · `git reset` · `git revert` · `git stash` · `git tag` · `git clean`

**CRITICAL**: Never execute state-changing commands without explicit user approval.

---

## Read-Only Commands: Always OK

`git status` · `git diff` · `git log` · `git branch` · `git show` · `git remote -v`

---

## How to Ask

1. Run `git status` and `git diff HEAD` to show current state
2. Propose the exact command: "Should I run `git <command> <args>`?"
3. Wait for "Yes" before proceeding
