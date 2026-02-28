---
name: git_summary
description: Prepare high-quality git commit messages or comprehensive Pull Request (PR) descriptions based on recent changes.
disable-model-invocation: true
user-invocable: true
---
# Skill: git_summary
When this skill is activated, you assist the user in drafting professional version control summaries.

## Workflow
1.  **Diff Analysis**: Run `git status` and `git diff` (or `git log`) to thoroughly understand the changes since the last commit or base branch.
2.  **Impact Analysis**: Detail the features added, bugs fixed, and testing evidence.
3.  **Drafting**: 
    - **For Commits**: 
        - Create a message with a concise subject line (imperative mood) and a body explaining the "why".
        - Provide the user with the exact command to execute using the following format:
          ```bash
          git commit -m "$(cat <<'EOF'
          [Subject line]

          [Body explaining the why]
          EOF
          )"
          ```
    - **For PRs**: Create a comprehensive markdown description summarizing all modifications, impacts, and testing evidence.
4.  **Refinement**: Ensure the message follows project standards.

**Note**: Do not perform the commit or create the PR yourself; provide the draft and command for the user to review and execute.