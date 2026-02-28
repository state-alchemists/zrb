# Git Operations Protocol: ABSOLUTE RULES

## 1. ABSOLUTE PROHIBITIONS
1.  **NEVER modify git state without EXPLICIT VERBAL approval.** No staging, committing, pushing, pulling, checking out, resetting, merging, tagging, or stashing.
2.  **Task completion NEVER includes git ops.** "Update docs" ≠ permission to stage/commit docs.
3.  **Each git op requires SEPARATE approval.** Staging ≠ permission to commit.

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
