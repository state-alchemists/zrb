# Git Command Guidelines

## Core Principles

- **Safety First:** Always verify current branch and status before destructive operations
- **Atomic Commits:** Each commit should represent a single logical change
- **Descriptive Messages:** Write clear, concise commit messages that explain "why" not just "what"
- **Interactive Mode:** Use interactive rebase and staging for precise control

## Essential Commands

### Repository Status
```bash
# Check current status and branch
git status
git branch -v

# See uncommitted changes
git diff
git diff --staged
```

### Safe Branch Operations
```bash
# Create and switch to new branch
git checkout -b feature/new-feature

# Switch branches safely
git switch main
git switch feature/branch-name

# List all branches
git branch -a
```

### Staging and Committing
```bash
# Stage specific files
git add path/to/file.py
git add src/

# Stage interactively
git add -p

# Commit with descriptive message
git commit -m "feat: add user authentication

- Implement JWT token generation
- Add login/logout endpoints
- Add password hashing"

# Amend last commit (use carefully)
git commit --amend
```

### History and Logs
```bash
# View commit history
git log --oneline --graph -10
git log --stat

# See who changed what
git blame file.py
```

## Advanced Operations

### Rebasing and Merging
```bash
# Update feature branch from main
git switch feature/branch
git rebase main

# Interactive rebase for cleanup
git rebase -i HEAD~5

# Safe merge
git merge --no-ff feature/branch
```

### Stashing
```bash
# Save uncommitted changes temporarily
git stash push -m "WIP: feature implementation"

# List stashes
git stash list

# Apply and keep stash
git stash apply stash@{0}

# Apply and drop stash
git stash pop
```

### Remote Operations
```bash
# Fetch and check before pulling
git fetch origin
git log origin/main..main

# Push safely
git push origin feature/branch
git push --force-with-lease  # Safer than --force
```

## Safety Checklist

1. **Before destructive operations:** Always run `git status` and `git branch -v`
2. **Before force push:** Use `--force-with-lease` instead of `--force`
3. **Before rebase:** Ensure working directory is clean
4. **Before merge:** Resolve conflicts immediately
5. **Regularly:** Fetch and integrate upstream changes

## Common Patterns

### Feature Development
```bash
git checkout -b feature/new-feature
# ... make changes ...
git add .
git commit -m "feat: implement new feature"
git push origin feature/new-feature
```

### Hotfix Workflow
```bash
git checkout -b hotfix/critical-bug main
# ... fix the bug ...
git add .
git commit -m "fix: resolve critical issue"
git push origin hotfix/critical-bug
```

### Cleanup
```bash
# Delete merged branches locally
git branch --merged main | grep -v "main" | xargs git branch -d

# Delete remote branches
git push origin --delete old-branch
```