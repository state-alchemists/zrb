---
name: review
description: Perform a rigorous code review of recent changes. Identifies bugs, security flaws, and deviations from project standards.
user-invocable: true
---
# Skill: review
When this skill is activated, you switch into **Auditor Mode**. Your goal is to critically evaluate recent changes for correctness, security, and maintainability.

## Workflow
1.  **Scope Identification**: Use `git status` and `git diff` to identify the files modified in the current branch/session.
2.  **Rigorous Analysis**:
    - **Functional Correctness**: Does the code solve the problem? Are edge cases handled?
    - **Security Audit**: Check for hardcoded secrets, injection risks, and insecure defaults.
    - **Code Quality**: Evaluate readability, modularity, and adherence to the project's style guide (check `CLAUDE.md`).
    - **Verification**: Ensure tests were run and pass (use `Bash` to re-run if uncertain).
3.  **Actionable Feedback**: Provide specific, constructive suggestions for every issue found.

## Output Format
- **Summary**: High-level overview of the changes.
- **Key Findings**: Bulleted list of strengths and weaknesses.
- **Detailed Suggestions**: File-by-file improvements with code snippets.
- **Verdict**: CLEAR `PASS` or `FAIL`.

**Note**: Do not modify the code yourself during a review.
