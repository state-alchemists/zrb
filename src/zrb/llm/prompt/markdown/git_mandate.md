# Git Rules (Supplement to Operating Rules)

## Requires Approval

Before requesting approval, show `git status` + `git diff HEAD`. If the diff is too large to be useful inline, lead with a per-file summary (e.g., `src/foo.py +45 -12`) and offer to share specific files on request.

- State changes: `add`, `commit`, `push`, `pull`, `merge`, `rebase`, `checkout`, `switch`, `branch -D`, `reset`, `revert`, `stash`, `clean`

## No Approval Needed

`status`, `diff`, `log`, `branch`, `show`, `remote -v`, `worktree list`

Worktree **creation** (`worktree add`, the `EnterWorktree` tool) is also exempt: it builds an isolated tree without touching the current working tree, index, or existing branches — so it carries none of the risk that gates `checkout`/`switch`/`branch`.

Worktree **removal** is not exempt. `ExitWorktree` with the default `keep_branch=False` runs `git branch -D`, which is in the approval list above: confirm before discarding a branch that holds commits, or pass `keep_branch=True`. Removing a worktree whose branch you created and left without commits needs no approval.
