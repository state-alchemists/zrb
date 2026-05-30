# Commit Message Template

Use when drafting a git commit message. Always check the project's recent log with `git log --oneline -20` first — match the project's style (conventional commits, plain imperative, ticket prefixes).

## Default Format (Conventional Commits)

```
<type>(<scope>): <subject>

<body — wrap at 72 columns>

<optional footer: BREAKING CHANGE, Closes #N, Co-Authored-By>
```

### Types

| Type | When |
|------|------|
| `feat` | A new user-visible feature |
| `fix` | A bug fix |
| `refactor` | Restructuring with no behavior change |
| `perf` | Performance improvement |
| `test` | Adding or fixing tests only |
| `docs` | Documentation only |
| `chore` | Build, deps, tooling — nothing user-visible |
| `style` | Whitespace, formatting (rare; usually `chore`) |
| `build` | Build system or external dependencies |
| `ci` | CI configuration |

### Subject Line

- ≤ 50 characters
- Imperative mood: "add", "fix", "remove" — not "added" or "adds"
- No trailing period
- Lowercase after the colon
- Says *what changed*, not *why*

Good: `fix(auth): reject expired JWTs before signature check`
Bad:  `Fixed a bug where expired JWTs were being processed.`

### Body

- Wrap at 72 columns
- Explain *why*, not *what* (the diff shows what)
- Reference the problem this commit solves
- Note non-obvious decisions and rejected alternatives
- Omit the body entirely for trivial commits ("docs: fix typo")

### Footer

- `BREAKING CHANGE: <description>` for any backward-incompatible change
- `Closes #N` to auto-close issues
- `Co-Authored-By: Name <email>` if collaborative

## Plain Imperative Format (No Conventional Prefix)

For projects that don't use conventional commits, just drop the `<type>(<scope>):` prefix:

```
Reject expired JWTs before signature check

The signature path was running first, which leaked timing
information about token validity. Move the expiry check
ahead so all invalid tokens reach the failure branch in
constant time.

Closes #1234
```

Same rules: imperative subject ≤50 chars, blank line, wrapped body.

## What to Avoid

- "Various changes" / "Updates" — uninformative subjects
- WIP commits in the final history — squash before merge
- Subjects that mix unrelated changes — split into multiple commits
- Body that describes the diff line by line — the reader has the diff
- Capitalized type prefix (`Feat:` instead of `feat:`)

## Multi-Line Commit via Heredoc

When proposing a commit command, use a heredoc so newlines survive shell parsing:

```bash
git commit -m "$(cat <<'EOF'
fix(auth): reject expired JWTs before signature check

The signature path was running first, which leaked timing
information about token validity.

Closes #1234
EOF
)"
```
