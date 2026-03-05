# 🐙 Absolute Git Rule

## 1. Prohibitions & Mandatory Approvals
1.  **NEVER execute ANY git command that changes repository state without EXPLICIT VERBAL approval for THAT SPECIFIC command.** 
    *Examples of state changes: `git add`, `git commit`, `git push`, `git checkout`, `git reset`, `git merge`, `git stash`.*
2.  **Task completion does NOT imply git permission.** Explicit approval is strictly mandatory for every single state-changing operation (e.g., "Update docs" does NOT mean you can stage/commit docs).
3.  **Read-Only Permitted:** You may run info-gathering commands without approval (`git status`, `git diff`, `git log`, `git branch`).

## 2. Strict Approval Protocol
1.  **Check Status:** Always run `git status && git diff HEAD` to understand the current state before proposing a change.
2.  **Propose Exactly:** Ask the user with the exact command (e.g., "Should I run `git add config.py test.py`?").
3.  **Await "Yes":** Only proceed if the user gives explicit, unambiguous approval. Silence or vague agreement is NOT approval.

## 3. Violation Response
If you violate these rules: STOP IMMEDIATELY, report the violation to the user, revert the changes, and await correction. Assist, do not autonomously manage git.
