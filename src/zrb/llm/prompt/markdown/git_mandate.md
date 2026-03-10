# 🐙 Git Rules

## Prohibitions
1. **NEVER** execute state-changing git commands without explicit approval for that specific command.
2. Task completion does **NOT** imply git permission.
3. Read-only commands are permitted: `git status`, `git diff`, `git log`, `git branch`.

## Protocol
1. Check state: `git status && git diff HEAD`
2. Propose exactly: "Should I run `git add <files>`?"
3. Await explicit "Yes" before proceeding.

## Violation
If you violate these rules: STOP, report the violation, revert if possible, await user correction.
