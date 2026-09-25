import os
from datetime import datetime
from typing import Annotated

from pydantic import Field

from zrb.config.config import CFG
from zrb.llm.sandbox import build_sandboxed_argv, get_effective_sandbox_policy
from zrb.llm.sandbox.os_sandbox import (
    SandboxUnavailableError,
    format_sandbox_denied_message,
)
from zrb.llm.tool.ambient_state import active_worktree
from zrb.llm.tool.shell import start_process


async def enter_worktree(
    branch_name: Annotated[
        str,
        Field(
            description=(
                "Branch to create; auto-generated (worktree-YYYYMMDD-HHMMSS) "
                "when empty."
            )
        ),
    ] = "",
    cwd: Annotated[
        str, Field(description="Repo root to operate in, if not the current directory.")
    ] = "",
) -> str:
    """
    Creates an isolated git worktree on a new branch and returns its path.
    """

    cwd = cwd or os.getcwd()
    notes: list[str | None] = []

    try:
        root_rc, root_out, _, note = await _run_git(
            ["git", "rev-parse", "--show-toplevel"], cwd
        )
    except SandboxUnavailableError as e:
        return format_sandbox_denied_message(e)
    notes.append(note)
    if root_rc != 0:
        return _prepend_notes(
            notes,
            "Error: Not inside a git repository.\n"
            "[SYSTEM SUGGESTION]: Navigate to a directory that is a git repository root, "
            "or provide cwd pointing to one.",
        )

    git_root = root_out.decode().strip()

    if not branch_name:
        branch_name = f"worktree-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    worktree_dir = os.path.join(git_root, f".{CFG.ROOT_GROUP_NAME}", "worktree")
    os.makedirs(worktree_dir, exist_ok=True)
    worktree_path = os.path.join(worktree_dir, branch_name)

    try:
        # sandbox_cwd=git_root: that's where the worktree is actually created.
        add_rc, _, add_err, note = await _run_git(
            ["git", "worktree", "add", "-b", branch_name, worktree_path],
            cwd,
            sandbox_cwd=git_root,
        )
    except SandboxUnavailableError as e:
        return _prepend_notes(notes, format_sandbox_denied_message(e))
    notes.append(note)
    if add_rc != 0:
        err_msg = add_err.decode().strip()
        if "already exists" in err_msg.lower():
            return _prepend_notes(
                notes,
                f"Error: Worktree or branch '{branch_name}' already exists.\n"
                f"[SYSTEM SUGGESTION]: Use a different branch_name or list existing worktrees with ListWorktrees.",
            )
        return _prepend_notes(
            notes,
            f"Error: Failed to create worktree: {err_msg}\n"
            f"[SYSTEM SUGGESTION]: Check if the branch name is valid and if you have permissions.",
        )

    active_worktree.set(worktree_path)
    _ensure_gitignore(git_root, f".{CFG.ROOT_GROUP_NAME}/worktree/")
    result = f"Worktree created: {worktree_path}\nBranch: {branch_name}"
    return _prepend_notes(notes, result)


async def exit_worktree(
    worktree_path: Annotated[
        str,
        Field(
            description="Path of the worktree to remove, as returned by EnterWorktree."
        ),
    ],
    keep_branch: Annotated[
        bool,
        Field(
            description=(
                "False (default) also runs `git branch -D` — the branch and all "
                "its commits are gone, irreversibly. Pass True to keep the branch."
            )
        ),
    ] = False,
) -> str:
    """
    Removes a worktree created with EnterWorktree.

    Confirm with the user before discarding a branch that holds commits, and pass
    keep_branch=True when unsure. Removing a worktree you created and left empty
    needs no confirmation.
    """
    cwd = os.getcwd()
    notes: list[str | None] = []

    if not os.path.isdir(worktree_path):
        return (
            f"Error: Worktree path does not exist: {worktree_path}\n"
            f"[SYSTEM SUGGESTION]: Use ListWorktrees to see active worktrees and their exact paths."
        )

    try:
        branch_rc, branch_out, _, note = await _run_git(
            ["git", "-C", worktree_path, "rev-parse", "--abbrev-ref", "HEAD"], cwd
        )
    except SandboxUnavailableError as e:
        return format_sandbox_denied_message(e)
    notes.append(note)
    branch_name = branch_out.decode().strip() if branch_rc == 0 else None

    try:
        git_root = await _resolve_git_root(worktree_path, cwd, notes)
    except SandboxUnavailableError as e:
        return _prepend_notes(notes, format_sandbox_denied_message(e))

    try:
        rm_rc, _, rm_err, note = await _run_git(
            ["git", "worktree", "remove", "--force", worktree_path],
            cwd,
            sandbox_cwd=git_root,
        )
    except SandboxUnavailableError as e:
        return _prepend_notes(notes, format_sandbox_denied_message(e))
    notes.append(note)
    if rm_rc != 0:
        return _prepend_notes(
            notes,
            f"Error: Failed to remove worktree: {rm_err.decode().strip()}\n"
            f"[SYSTEM SUGGESTION]: Ensure no uncommitted changes are in the worktree, "
            f"then retry. Use ListWorktrees to check status.",
        )

    # The worktree removal above already succeeded (rm_rc == 0): that result
    # must survive from here on even if the branch-delete step below fails
    # or hits SandboxUnavailableError — this function must never turn an
    # already-true "Worktree removed" into an outright error.
    active_worktree.set("")
    lines = [f"Worktree removed: {worktree_path}"]

    if branch_name:
        lines.append(
            await _delete_branch_line(branch_name, keep_branch, cwd, git_root, notes)
        )
    return _prepend_notes(notes, "\n".join(lines))


async def _resolve_git_root(
    worktree_path: str, cwd: str, notes: "list[str | None]"
) -> str:
    """The main repo's root, which worktree-admin and branch commands anchor to.

    `--git-common-dir` names the main repo's `.git` dir, where `worktree
    remove` updates worktree-admin metadata and `branch -D` updates refs.
    Neither necessarily lives under `cwd` (the caller may be anywhere) or under
    `worktree_path` itself, so — mirroring `enter_worktree`'s
    `sandbox_cwd=git_root` for its `worktree add` — both anchor to its parent
    rather than the bare process cwd. Falls back to `cwd` when git cannot say.
    """
    common_rc, common_out, _, note = await _run_git(
        ["git", "-C", worktree_path, "rev-parse", "--git-common-dir"], cwd
    )
    notes.append(note)
    git_common_dir = common_out.decode().strip()
    if common_rc != 0 or not git_common_dir:
        return cwd
    if not os.path.isabs(git_common_dir):
        git_common_dir = os.path.normpath(os.path.join(worktree_path, git_common_dir))
    return os.path.dirname(git_common_dir)


async def _delete_branch_line(
    branch_name: str,
    keep_branch: bool,
    cwd: str,
    git_root: str,
    notes: "list[str | None]",
) -> str:
    """Delete the worktree's branch if asked, and report what happened.

    Never raises: the worktree removal has already succeeded by the time this
    runs, and that result must survive a failure here.
    """
    if keep_branch:
        return f"Branch kept: {branch_name}"
    try:
        del_rc, _, del_err, note = await _run_git(
            ["git", "branch", "-D", branch_name], cwd, sandbox_cwd=git_root
        )
    except SandboxUnavailableError as e:
        refused = format_sandbox_denied_message(e)
        return f"Branch kept: {branch_name} (could not delete — {refused})"
    notes.append(note)
    if del_rc == 0:
        return f"Branch deleted: {branch_name}"
    return (
        f"Branch kept: {branch_name} "
        f"(could not delete — {del_err.decode().strip()})"
    )


async def list_worktrees() -> str:
    """
    Lists all active git worktrees for the current repository (path, branch, commit).
    """
    cwd = os.getcwd()

    try:
        returncode, stdout, _, note = await _run_git(["git", "worktree", "list"], cwd)
    except SandboxUnavailableError as e:
        return format_sandbox_denied_message(e)
    if returncode != 0:
        return _prepend_notes(
            [note],
            "Error: Not inside a git repository.\n"
            "[SYSTEM SUGGESTION]: Navigate to a git repository root.",
        )

    output = stdout.decode().strip()
    result = output if output else "No worktrees found (only the main working tree)."
    return _prepend_notes([note], result)


async def _run_git(
    argv: list[str], cwd: str, sandbox_cwd: str | None = None
) -> tuple[int | None, bytes, bytes, str | None]:
    """Run a git command through the same OS-level sandbox `Shell` uses.

    Discrete argv, not a shell string, so branch/path values never need
    quoting. `sandbox_cwd` overrides `cwd` as the sandbox's writable-root
    anchor when the real write target differs (e.g. `worktree add` writes
    under `git_root`). Raises `SandboxUnavailableError` in fallback="deny"
    mode; callers turn it into a `[SYSTEM SUGGESTION]`.
    """
    sandboxed_argv, note = build_sandboxed_argv(
        argv, sandbox_cwd or cwd, get_effective_sandbox_policy()
    )
    proc = await start_process(sandboxed_argv, cwd)
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout, stderr, note


def _prepend_notes(notes: list[str | None], result: str) -> str:
    """Prepend every collected note (in call order), not just the first —
    an earlier git call's sandbox-fallback warning must still reach the
    model even when a later call in the same tool invocation errors, or
    also produces its own note.
    """
    text = "\n".join(n for n in notes if n)
    return f"{text}\n{result}" if text else result


def _ensure_gitignore(git_root: str, pattern: str) -> None:
    """Add pattern to {git_root}/.gitignore if not already present."""
    gitignore_path = os.path.join(git_root, ".gitignore")
    try:
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r", encoding="utf-8") as f:
                content = f.read()
            lines = content.splitlines()
            if any(line.strip() == pattern for line in lines):
                return
            with open(gitignore_path, "a", encoding="utf-8") as f:
                prefix = "\n" if content and not content.endswith("\n") else ""
                f.write(f"{prefix}{pattern}\n")
        else:
            with open(gitignore_path, "w", encoding="utf-8") as f:
                f.write(f"{pattern}\n")
    except OSError:
        pass


enter_worktree.__name__ = "EnterWorktree"
exit_worktree.__name__ = "ExitWorktree"
list_worktrees.__name__ = "ListWorktrees"
