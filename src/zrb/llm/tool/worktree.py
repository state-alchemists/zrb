import hashlib
import os
from datetime import datetime
from typing import Annotated

from pydantic import Field

from zrb.config.config import CFG
from zrb.llm.ambient_state import active_worktree
from zrb.llm.sandbox import (
    build_sandboxed_argv,
    check_write,
    get_effective_sandbox_policy,
    resolve_real,
)
from zrb.llm.sandbox.os_sandbox import (
    SandboxUnavailableError,
    format_sandbox_denied_message,
)
from zrb.llm.tool.shell import start_process

_MAIN_WORKTREE_ERROR = (
    "Error: The main working tree cannot be resumed as a linked worktree. "
    "Pass a path from ListWorktrees that is a linked worktree."
)


async def enter_worktree(
    branch_name: Annotated[
        str, Field(description="Branch to create; auto-named when empty.")
    ] = "",
    worktree_path: Annotated[
        str, Field(description="Existing worktree to resume instead of creating.")
    ] = "",
    cwd: Annotated[
        str, Field(description="Repo root, if not the current directory.")
    ] = "",
) -> str:
    """
    Creates a new isolated git worktree, or resumes an existing linked worktree.

    New worktrees live under ``~/.zrb/wt/<repo>-<digest>/``, outside the
    checkout: a worktree nested inside the repository is a second copy of the
    repo inside the repo, which every ``Grep``, ``Glob`` and ``git status``
    then has to learn to ignore.

    Pass ``worktree_path`` from ``ListWorktrees`` to continue work in place;
    ``ExitWorktree`` removes one.
    """

    if branch_name and worktree_path:
        return (
            "Error: branch_name and worktree_path cannot be used together. "
            "Pass worktree_path to resume an existing worktree, or branch_name "
            "to create one."
        )

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
    if worktree_path:
        return await _resume_worktree(worktree_path, git_root, cwd, notes)

    error = _repo_write_error(git_root)
    if error is not None:
        return _prepend_notes(notes, error)

    if not branch_name:
        branch_name = f"worktree-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    worktree_path, error = _prepare_worktree_dir(git_root, branch_name)
    if error is not None:
        return _prepend_notes(notes, error)

    try:
        add_rc, _, add_err, note = await _run_git(
            ["git", "worktree", "add", "-b", branch_name, worktree_path], cwd
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
                "[SYSTEM SUGGESTION]: Use a different branch_name or list existing "
                "worktrees with ListWorktrees.",
            )
        return _prepend_notes(notes, _create_failed_message(err_msg, git_root))

    active_worktree.set(worktree_path)
    result = f"Worktree created: {worktree_path}\nBranch: {branch_name}"
    return _prepend_notes(notes, result)


def _create_failed_message(err_msg: str, git_root: str) -> str:
    """Explain a failed `git worktree add`, including the sandbox's second write.

    A worktree is not written only where it lands. git records the new branch and
    the worktree's own administrative files inside the repository, so a sandbox
    session that lists the worktree root alone is stopped here by git rather than
    by our own check — and git's message names a `.git` lock, not a policy.
    """
    suggestion = "Check if the branch name is valid and if you have permissions."
    policy = get_effective_sandbox_policy()
    if (
        policy.enabled
        and check_write(os.path.join(git_root, ".git"), policy) is not None
    ):
        suggestion = (
            f"git writes the new branch and the worktree's records into the "
            f"repository, so the sandbox has to allow that too: add {git_root} to "
            f"{CFG.ENV_PREFIX}_LLM_SANDBOX_WRITABLE_PATHS alongside "
            f"{_worktree_root()}, or leave that setting empty: the automatic "
            "roots include the current directory and the worktree root."
        )
    return (
        f"Error: Failed to create worktree: {err_msg}\n"
        f"[SYSTEM SUGGESTION]: {suggestion}"
    )


def _repo_slug(git_root: str) -> str:
    """``<repo>-<digest>`` — the repository's own directory under the worktree root.

    The basename alone is not unique: two checkouts named `api` would share one
    directory and the second `git worktree add` would fail on a path it does not
    own. The digest comes from the canonical path, so it survives a rename of the
    directory the repository sits in only if the path really is the same repo.
    """
    real_root = os.path.realpath(git_root)
    name = os.path.basename(real_root) or "repo"
    digest = hashlib.sha256(real_root.encode("utf-8")).hexdigest()[:8]
    return f"{name}-{digest}"


def _worktree_root() -> str:
    """The configured root for linked worktrees, as an absolute canonical path.

    ``LLM_WORKTREE_DIR`` may be relative or use ``~``. It is resolved once
    here, so the sandbox check, ``os.makedirs`` and the path handed to git all
    name the same directory: git resolves a relative destination against the
    ``cwd`` it is given, which is not the process directory the check used.
    """
    return resolve_real(CFG.LLM_WORKTREE_DIR)


def _worktree_parent(git_root: str) -> str:
    """``<LLM_WORKTREE_DIR>/<repo>-<digest>`` — where linked worktrees live.

    Outside the checkout by default: a worktree nested in the repository is a
    second copy of it that every search has to skip. Namespaced by repository:
    an auto-named branch is a timestamp, so one flat directory would let two
    projects collide on the same branch name.
    """
    return os.path.join(_worktree_root(), _repo_slug(git_root))


def _repo_write_error(git_root: str) -> str | None:
    """Refuse before git writes a branch into a repository the sandbox forbids.

    A worktree is not written only where it lands: `git worktree add` records
    the new branch and the worktree's administrative files inside the
    repository. The gate judges the model's `cwd`, which names a directory and
    can be a subdirectory whose repository root is outside the writable roots,
    so the root git itself revealed is judged here — before anything is created.
    """
    policy = get_effective_sandbox_policy()
    if not policy.enabled:
        return None
    error = check_write(git_root, policy)
    if error is None:
        return None
    return (
        f"Blocked by sandbox policy: {error}. "
        "[SYSTEM SUGGESTION]: a worktree is not written only where it lands — "
        "git records the new branch and the worktree inside the repository, so "
        f"add {git_root} to {CFG.ENV_PREFIX}_LLM_SANDBOX_WRITABLE_PATHS."
    )


def _prepare_worktree_dir(git_root: str, branch_name: str) -> tuple[str, str | None]:
    """Resolve, judge and create the destination; return (path, error).

    ``branch_name`` is the model's choice, so the resulting path is judged
    against the sandbox *before* anything is created on disk.
    """
    worktree_dir = _worktree_parent(git_root)
    worktree_path = os.path.join(worktree_dir, branch_name)
    # One level up is the worktree root; suggesting that covers every repository
    # at once, where suggesting this repository's own directory would not.
    root = os.path.dirname(worktree_dir)
    policy = get_effective_sandbox_policy()
    if policy.enabled:
        error = check_write(worktree_path, policy)
        if error is not None:
            return worktree_path, (
                f"Blocked by sandbox policy: {error}. "
                f"[SYSTEM SUGGESTION]: ask the user to add {root} to "
                f"{CFG.ENV_PREFIX}_LLM_SANDBOX_WRITABLE_PATHS — and keep {git_root} "
                "writable too, since git records the branch and the worktree "
                "inside the repository. The automatic (empty) list already "
                "includes the worktree root."
            )
    try:
        os.makedirs(worktree_dir, exist_ok=True)
    except OSError as e:
        return worktree_path, (
            f"Error: Cannot create worktree directory {worktree_dir}: {e}\n"
            "[SYSTEM SUGGESTION]: check that the home directory is writable."
        )
    return worktree_path, None


async def _resume_worktree(
    worktree_path: str,
    git_root: str,
    cwd: str,
    notes: list[str | None],
) -> str:
    """Select a registered linked worktree without creating or removing it."""
    requested_path = os.path.realpath(worktree_path)
    if not os.path.isdir(requested_path):
        return (
            f"Error: Existing worktree was not found: {worktree_path}\n"
            "[SYSTEM SUGGESTION]: Use ListWorktrees to see active worktrees and "
            "their exact paths."
        )
    if requested_path == os.path.realpath(git_root):
        return _MAIN_WORKTREE_ERROR

    policy = get_effective_sandbox_policy()
    if policy.enabled:
        error = check_write(requested_path, policy)
        if error is not None:
            return _prepend_notes(
                notes,
                f"Blocked by sandbox policy: {error}. "
                "[SYSTEM SUGGESTION]: ask the user to add this worktree to "
                f"{CFG.ENV_PREFIX}_LLM_SANDBOX_WRITABLE_PATHS.",
            )

    try:
        list_rc, list_out, list_err, note = await _run_git(
            ["git", "worktree", "list", "--porcelain"], cwd
        )
    except SandboxUnavailableError as e:
        return _prepend_notes(notes, format_sandbox_denied_message(e))
    notes.append(note)
    if list_rc != 0:
        return _prepend_notes(
            notes,
            f"Error: Failed to list worktrees: {list_err.decode().strip()}\n"
            "[SYSTEM SUGGESTION]: Use ListWorktrees to inspect the repository's "
            "active worktrees.",
        )

    worktree_list = list_out.decode()
    if _find_main_worktree_path(worktree_list) == requested_path:
        return _prepend_notes(notes, _MAIN_WORKTREE_ERROR)

    branch_name = _find_worktree_branch(worktree_list, requested_path)
    if branch_name is None:
        return _prepend_notes(
            notes,
            f"Error: Existing worktree was not found: {worktree_path}\n"
            "[SYSTEM SUGGESTION]: Use ListWorktrees to see active worktrees and "
            "their exact paths.",
        )

    active_worktree.set(requested_path)
    return _prepend_notes(
        notes, f"Worktree resumed: {worktree_path}\nBranch: {branch_name}"
    )


def _find_main_worktree_path(worktree_list: str) -> str | None:
    """Return the main worktree path, the first porcelain entry."""
    for line in worktree_list.splitlines():
        if line.startswith("worktree "):
            return os.path.realpath(line.removeprefix("worktree "))
    return None


def _find_worktree_branch(worktree_list: str, requested_path: str) -> str | None:
    """Return the branch for *requested_path* in porcelain worktree output."""
    current_path = ""
    current_branch = "HEAD (detached)"
    for line in (*worktree_list.splitlines(), ""):
        if line.startswith("worktree "):
            current_path = os.path.realpath(line.removeprefix("worktree "))
            current_branch = "HEAD (detached)"
            continue
        if line.startswith("branch "):
            current_branch = line.removeprefix("branch refs/heads/")
            continue
        if not line and current_path:
            if current_path == requested_path:
                return current_branch
            current_path = ""
    return None


async def exit_worktree(
    worktree_path: Annotated[str, Field(description="Path from EnterWorktree.")],
    keep_branch: Annotated[
        bool,
        Field(
            description=(
                "False also runs `git branch -D` — the branch and its commits "
                "are gone, irreversibly."
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
            "[SYSTEM SUGGESTION]: Use ListWorktrees to see active worktrees and "
            "their exact paths."
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
        rm_rc, _, rm_err, note = await _run_git(
            ["git", "worktree", "remove", "--force", worktree_path], cwd
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

    active_worktree.set("")
    lines = [f"Worktree removed: {worktree_path}"]

    if branch_name:
        lines.append(await _delete_branch_line(branch_name, keep_branch, cwd, notes))
    return _prepend_notes(notes, "\n".join(lines))


async def _delete_branch_line(
    branch_name: str,
    keep_branch: bool,
    cwd: str,
    notes: "list[str | None]",
) -> str:
    """Delete the worktree's branch if asked, and report what happened.

    Never raises: the worktree removal has already succeeded.
    """
    if keep_branch:
        return f"Branch kept: {branch_name}"
    try:
        del_rc, _, del_err, note = await _run_git(
            ["git", "branch", "-D", branch_name], cwd
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
    argv: list[str], cwd: str
) -> tuple[int | None, bytes, bytes, str | None]:
    """Run a git argv through the same OS-level sandbox `Shell` uses.

    The writable boundary is the sandbox policy's, never the model-chosen
    `cwd`. Raises `SandboxUnavailableError` in fallback="deny" mode.
    """
    sandboxed_argv, note = build_sandboxed_argv(argv, get_effective_sandbox_policy())
    proc = await start_process(sandboxed_argv, cwd)
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout, stderr, note


def _prepend_notes(notes: list[str | None], result: str) -> str:
    """Prepend every collected sandbox note, in call order."""
    text = "\n".join(n for n in notes if n)
    return f"{text}\n{result}" if text else result


enter_worktree.__name__ = "EnterWorktree"
exit_worktree.__name__ = "ExitWorktree"
list_worktrees.__name__ = "ListWorktrees"
