# Git Operations Protocol: ABSOLUTE RULES

## 1. ABSOLUTE PROHIBITIONS
1.  **🚨 ABSOLUTE PROHIBITION: NEVER execute ANY git command that changes repository state without EXPLICIT VERBAL approval for THAT SPECIFIC command.** This includes but is not limited to: `git add` (STAGING - this is a state change!), `git commit`, `git push`/`git pull`, `git checkout`/`git reset`, `git merge`/`git rebase`, `git tag`/`git stash`.
2.  **Task completion NEVER includes git ops.** "Update docs" ≠ permission to stage/commit docs.
3.  **Each git operation requires SEPARATE approval.** Stage files" ≠ permission to commit. "Update code" ≠ permission to stage.

## 2. PERMITTED (READ-ONLY)
- `git status`, `git diff`, `git log`, `git show`, `git branch` (info only)

## 3. STRICT APPROVAL PROTOCOL
1.  **Always check status first:** `git status && git diff HEAD`
2.  **Propose EXACTLY:** "Should I `git add file1 file2`?" (be specific)
3.  **Await EXPLICIT "yes"/"proceed":** "Okay" ≠ approval. Silence ≠ approval.
4.  **Verify before executing:** Check `git diff --staged` if staging.

## 4. VIOLATION = SEVERE FAILURE
If you violate: STOP IMMEDIATELY, report violation, revert changes, await correction.

## 5. EXAMPLES
1. **Correct:** "Should I `git add config.py test.py`?" → User: "Yes" → Execute
2. **Incorrect:** "Update docs" → [Auto-stage] ❌ VIOLATION
3. **Incorrect:** "Should I commit?" → User: "Okay" → [Commit] ❌ VIOLATION

**REMEMBER:** Assist, don't autonomously manage git. When in doubt, ASK. Better to ask repeatedly than violate once.
