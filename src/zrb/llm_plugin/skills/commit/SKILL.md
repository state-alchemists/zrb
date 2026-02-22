---
name: commit
description: Prepare a high-quality git commit message. Use when asked to draft a commit message for staged or recent changes.
disable-model-invocation: true
user-invocable: true
---
# Skill: commit
When this skill is activated, you assist the user in drafting a professional git commit message.

## Workflow
1.  **Diff Analysis**: Run `git status` and `git diff` to understand the changes.
2.  **Drafting**: Create a message with a concise subject line (imperative mood) and a body explaining the "why".
3.  **Refinement**: Ensure the message follows project standards.

**Note**: Do not perform the commit; provide the message for the user.
