import asyncio
import os
import shutil
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.prompt.live_context import render_live_context
from zrb.llm.sandbox.os_sandbox import SandboxUnavailableError
from zrb.llm.tool.worktree import enter_worktree, exit_worktree, list_worktrees


@pytest.fixture
def mock_subprocess():
    with patch("asyncio.create_subprocess_exec") as mock:
        yield mock


def create_mock_process(returncode=0, stdout=b"", stderr=b""):
    process = MagicMock()
    process.returncode = returncode
    process.communicate = AsyncMock(return_value=(stdout, stderr))
    return process


@pytest.mark.asyncio
async def test_enter_worktree_success(mock_subprocess):
    mock_subprocess.side_effect = [
        create_mock_process(returncode=0),  # check repo
        create_mock_process(
            returncode=0, stdout=b"Preparing worktree", stderr=b""
        ),  # git worktree add
    ]

    res = await enter_worktree(branch_name="test-branch")
    assert "Worktree created:" in res
    assert "Branch: test-branch" in res


@pytest.mark.asyncio
async def test_enter_worktree_no_branch_name(mock_subprocess):
    mock_subprocess.side_effect = [
        create_mock_process(returncode=0),  # check repo
        create_mock_process(returncode=0),  # git worktree add
    ]
    res = await enter_worktree()
    assert "Worktree created:" in res
    assert "Branch: worktree-" in res


@pytest.mark.asyncio
async def test_enter_worktree_not_repo(mock_subprocess):
    mock_subprocess.return_value = create_mock_process(
        returncode=1, stderr=b"fatal: not a git repository"
    )
    res = await enter_worktree()
    assert "Error" in res
    assert "git repository" in res


@pytest.mark.asyncio
async def test_enter_worktree_failure(mock_subprocess):
    mock_subprocess.side_effect = [
        create_mock_process(returncode=0),  # check repo
        create_mock_process(
            returncode=1, stderr=b"fatal: branch already exists"
        ),  # git worktree add
    ]
    res = await enter_worktree(branch_name="existing-branch")
    assert "Error" in res
    assert "already exists" in res


@pytest.mark.asyncio
async def test_exit_worktree_success(mock_subprocess):
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_subprocess.side_effect = [
            create_mock_process(
                returncode=0, stdout=b"test-branch\n"
            ),  # git rev-parse branch
            create_mock_process(returncode=0),  # git worktree remove
            create_mock_process(returncode=0),  # git branch -D
        ]
        res = await exit_worktree(tmpdir)
        assert f"Worktree removed: {tmpdir}" in res
        assert "Branch deleted: test-branch" in res


@pytest.mark.asyncio
async def test_exit_worktree_keep_branch(mock_subprocess):
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_subprocess.side_effect = [
            create_mock_process(
                returncode=0, stdout=b"test-branch\n"
            ),  # git rev-parse branch
            create_mock_process(returncode=0),  # git worktree remove
        ]
        res = await exit_worktree(tmpdir, keep_branch=True)
        assert f"Worktree removed: {tmpdir}" in res
        assert "Branch kept: test-branch" in res


@pytest.mark.asyncio
async def test_exit_worktree_not_exists():
    res = await exit_worktree("/non/existent/path")
    assert "Error" in res
    assert "does not exist" in res


@pytest.mark.asyncio
async def test_exit_worktree_remove_failure(mock_subprocess):
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_subprocess.side_effect = [
            create_mock_process(
                returncode=0, stdout=b"test-branch\n"
            ),  # git rev-parse branch
            create_mock_process(
                returncode=1, stderr=b"error: worktree contains modified files"
            ),  # git worktree remove
        ]
        res = await exit_worktree(tmpdir)
        assert "Error" in res
        assert "modified files" in res


@pytest.mark.asyncio
async def test_exit_worktree_branch_delete_failure(mock_subprocess):
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_subprocess.side_effect = [
            create_mock_process(
                returncode=0, stdout=b"test-branch\n"
            ),  # git rev-parse branch
            create_mock_process(returncode=0),  # git worktree remove
            create_mock_process(
                returncode=1, stderr=b"error: branch not found"
            ),  # git branch -D
        ]
        res = await exit_worktree(tmpdir)
        assert f"Worktree removed: {tmpdir}" in res
        assert "could not delete" in res.lower()


@pytest.mark.asyncio
async def test_list_worktrees_success(mock_subprocess):
    mock_subprocess.return_value = create_mock_process(
        returncode=0, stdout=b"/path/to/repo main\n/path/to/worktree branch-name"
    )
    res = await list_worktrees()
    assert "/path/to/repo main" in res
    assert "/path/to/worktree branch-name" in res


@pytest.mark.asyncio
async def test_list_worktrees_empty(mock_subprocess):
    mock_subprocess.return_value = create_mock_process(returncode=0, stdout=b"")
    res = await list_worktrees()
    assert "No worktrees found" in res


@pytest.mark.asyncio
async def test_list_worktrees_failure(mock_subprocess):
    mock_subprocess.return_value = create_mock_process(
        returncode=1, stderr=b"fatal: not a git repository"
    )
    res = await list_worktrees()
    assert "Error" in res
    assert "git repository" in res


@pytest.mark.asyncio
async def test_enter_worktree_unexpected_exception_propagates(mock_subprocess):
    """worktree.py no longer catches unexpected exceptions itself (ADR-0057)
    — as a registered tool, create_safe_wrapper's own error=True handling
    takes over; as delegate.py's direct in-process call, asyncio.gather's
    return_exceptions=True already handles it. Either way, this function
    itself must let the exception through rather than swallow it into a
    plain string, which would corrupt delegate.py's `AgentTaskResult.error:
    str | None` contract if it were caught here and returned as a ToolReturn.
    """
    mock_subprocess.side_effect = OSError("no such file or directory")

    with pytest.raises(OSError):
        await enter_worktree(branch_name="test-branch")


def _capture_live_context(ctx=None) -> str:
    """Helper: render the live-context block (where worktree state now lives)."""
    if ctx is None:
        ctx = MagicMock()
        ctx.input.session = "test-session"
    return render_live_context(ctx)


@pytest.mark.asyncio
async def test_enter_worktree_adds_gitignore_entry(mock_subprocess):
    """EnterWorktree should add the worktree pattern to .gitignore if absent."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_subprocess.side_effect = [
            create_mock_process(returncode=0, stdout=tmpdir.encode()),
            create_mock_process(returncode=0),
        ]
        await enter_worktree(branch_name="gi-branch", cwd=tmpdir)

        gitignore = os.path.join(tmpdir, ".gitignore")
        assert os.path.exists(gitignore)
        content = open(gitignore).read()
        assert ".zrb/worktree/" in content


@pytest.mark.asyncio
async def test_enter_worktree_does_not_duplicate_gitignore_entry(mock_subprocess):
    """EnterWorktree should not add a duplicate line if the pattern is already present."""
    with tempfile.TemporaryDirectory() as tmpdir:
        gitignore = os.path.join(tmpdir, ".gitignore")
        with open(gitignore, "w") as f:
            f.write(".zrb/worktree/\n")

        mock_subprocess.side_effect = [
            create_mock_process(returncode=0, stdout=tmpdir.encode()),
            create_mock_process(returncode=0),
        ]
        await enter_worktree(branch_name="nodup-branch", cwd=tmpdir)

        content = open(gitignore).read()
        assert content.count(".zrb/worktree/") == 1


@pytest.mark.asyncio
async def test_enter_worktree_appends_to_existing_gitignore(mock_subprocess):
    """EnterWorktree should append to an existing .gitignore without clobbering it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        gitignore = os.path.join(tmpdir, ".gitignore")
        with open(gitignore, "w") as f:
            f.write("*.pyc\n__pycache__\n")

        mock_subprocess.side_effect = [
            create_mock_process(returncode=0, stdout=tmpdir.encode()),
            create_mock_process(returncode=0),
        ]
        await enter_worktree(branch_name="append-branch", cwd=tmpdir)

        content = open(gitignore).read()
        assert "*.pyc" in content
        assert "__pycache__" in content
        assert ".zrb/worktree/" in content


@pytest.mark.asyncio
async def test_enter_and_exit_worktree_reflected_in_live_context(mock_subprocess):
    """EnterWorktree shows active worktree in the live context; ExitWorktree clears it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        worktree_path = os.path.join(tmpdir, ".zrb", "worktree", "sc-branch")

        # Enter
        mock_subprocess.side_effect = [
            create_mock_process(returncode=0, stdout=tmpdir.encode()),
            create_mock_process(returncode=0),
        ]
        await enter_worktree(branch_name="sc-branch", cwd=tmpdir)
        os.makedirs(worktree_path, exist_ok=True)
        assert "Active worktree:" in _capture_live_context()

        # Exit
        os.makedirs(worktree_path, exist_ok=True)
        mock_subprocess.side_effect = [
            create_mock_process(returncode=0, stdout=b"sc-branch\n"),
            create_mock_process(returncode=0),
            create_mock_process(returncode=0),
        ]
        await exit_worktree(worktree_path)
        assert "Active worktree:" not in _capture_live_context()


@pytest.mark.asyncio
async def test_enter_worktree_routes_git_calls_through_sandbox(mock_subprocess):
    """worktree git subprocesses now go through the same OS-level sandbox
    `Shell` uses (ADR-0065), not a raw, unwrapped `create_subprocess_exec`.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_subprocess.side_effect = [
            create_mock_process(returncode=0, stdout=tmpdir.encode()),
            create_mock_process(returncode=0),
        ]
        with patch(
            "zrb.llm.tool.worktree.build_sandboxed_argv",
            side_effect=lambda argv, cwd, policy, skip=False: (argv, None),
        ) as mock_build:
            await enter_worktree(branch_name="test-branch", cwd=tmpdir)

        assert mock_build.call_count == 2
        first_argv, first_cwd, *_ = mock_build.call_args_list[0].args
        assert first_argv == ["git", "rev-parse", "--show-toplevel"]
        assert first_cwd == tmpdir
        second_argv, second_cwd, *_ = mock_build.call_args_list[1].args
        assert second_argv == [
            "git",
            "worktree",
            "add",
            "-b",
            "test-branch",
            os.path.join(tmpdir, ".zrb", "worktree", "test-branch"),
        ]
        # The worktree is created under git_root, not the caller's cwd — the
        # sandbox's writable-root fallback must anchor there.
        assert second_cwd == tmpdir


@pytest.mark.asyncio
async def test_exit_worktree_routes_git_calls_through_sandbox(mock_subprocess):
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_subprocess.side_effect = [
            create_mock_process(returncode=0, stdout=b"test-branch\n"),
            create_mock_process(returncode=0),
            create_mock_process(returncode=0),
        ]
        with patch(
            "zrb.llm.tool.worktree.build_sandboxed_argv",
            side_effect=lambda argv, cwd, policy, skip=False: (argv, None),
        ) as mock_build:
            await exit_worktree(tmpdir)

        argvs = [call.args[0] for call in mock_build.call_args_list]
        assert argvs[0][:2] == ["git", "-C"]
        assert argvs[1] == ["git", "worktree", "remove", "--force", tmpdir]
        assert argvs[2] == ["git", "branch", "-D", "test-branch"]


@pytest.mark.asyncio
async def test_list_worktrees_routes_git_calls_through_sandbox(mock_subprocess):
    mock_subprocess.return_value = create_mock_process(returncode=0, stdout=b"")
    with patch(
        "zrb.llm.tool.worktree.build_sandboxed_argv",
        side_effect=lambda argv, cwd, policy, skip=False: (argv, None),
    ) as mock_build:
        await list_worktrees()

    assert mock_build.call_args.args[0] == ["git", "worktree", "list"]


@pytest.mark.asyncio
async def test_enter_worktree_sandbox_unavailable_surfaces_as_error():
    """A deny-mode sandbox refuses via SandboxUnavailableError; the tool
    relays it as a [SYSTEM SUGGESTION] string rather than raising.
    """
    with patch(
        "zrb.llm.tool.worktree.build_sandboxed_argv",
        side_effect=SandboxUnavailableError("deny mode"),
    ):
        res = await enter_worktree(branch_name="test-branch")
    assert "refused by sandbox policy" in res
    assert "deny mode" in res


@pytest.mark.asyncio
async def test_exit_worktree_sandbox_unavailable_surfaces_as_error():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch(
            "zrb.llm.tool.worktree.build_sandboxed_argv",
            side_effect=SandboxUnavailableError("deny mode"),
        ):
            res = await exit_worktree(tmpdir)
    assert "refused by sandbox policy" in res
    assert "deny mode" in res


@pytest.mark.asyncio
async def test_list_worktrees_sandbox_unavailable_surfaces_as_error():
    with patch(
        "zrb.llm.tool.worktree.build_sandboxed_argv",
        side_effect=SandboxUnavailableError("deny mode"),
    ):
        res = await list_worktrees()
    assert "refused by sandbox policy" in res
    assert "deny mode" in res


@pytest.mark.asyncio
async def test_list_worktrees_prepends_sandbox_fallback_note(mock_subprocess):
    """A warn-mode fallback note (e.g. bwrap missing) reaches the model,
    mirroring shell.py's own sandbox_note prepending.
    """
    mock_subprocess.return_value = create_mock_process(
        returncode=0, stdout=b"/path/to/repo main"
    )
    with patch(
        "zrb.llm.tool.worktree.build_sandboxed_argv",
        side_effect=lambda argv, cwd, policy, skip=False: (
            argv,
            "[WARNING] sandbox unavailable (bwrap not installed)",
        ),
    ):
        res = await list_worktrees()
    assert res.startswith("[WARNING] sandbox unavailable")
    assert "/path/to/repo main" in res


@pytest.mark.asyncio
async def test_exit_worktree_keeps_success_when_branch_delete_sandbox_unavailable(
    mock_subprocess,
):
    """The worktree is already gone (rm_rc == 0) by the time the branch
    delete step runs — that success must survive even though the delete
    itself hits SandboxUnavailableError, instead of the function returning
    only the sandbox-refused error as if nothing had happened.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_subprocess.side_effect = [
            create_mock_process(returncode=0, stdout=b"test-branch\n"),
            create_mock_process(returncode=0),
        ]

        def fake_build(argv, cwd, policy, skip=False):
            if argv[:2] == ["git", "branch"]:
                raise SandboxUnavailableError("deny mode")
            return argv, None

        with patch(
            "zrb.llm.tool.worktree.build_sandboxed_argv", side_effect=fake_build
        ):
            res = await exit_worktree(tmpdir)

    assert "Worktree removed:" in res
    assert "Branch kept: test-branch" in res
    assert "could not delete" in res
    assert "refused by sandbox policy" in res
    assert "deny mode" in res


@pytest.mark.asyncio
async def test_enter_worktree_keeps_earlier_note_when_later_call_errors(
    mock_subprocess,
):
    """A sandbox-fallback warning from the first git call must still reach
    the model even when the second call fails outright — not only when the
    whole operation succeeds.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_subprocess.side_effect = [
            create_mock_process(returncode=0, stdout=tmpdir.encode()),
            create_mock_process(returncode=128, stderr=b"fatal: already exists"),
        ]

        def fake_build(argv, cwd, policy, skip=False):
            note = (
                "[WARNING] sandbox unavailable"
                if argv[0:2] == ["git", "rev-parse"]
                else None
            )
            return argv, note

        with patch(
            "zrb.llm.tool.worktree.build_sandboxed_argv", side_effect=fake_build
        ):
            res = await enter_worktree(branch_name="test-branch", cwd=tmpdir)

    assert res.startswith("[WARNING] sandbox unavailable")
    assert "already exists" in res


@pytest.mark.asyncio
async def test_run_git_spawns_with_shell_py_style_protections(mock_subprocess):
    """_run_git mirrors shell.py's _start_process: DEVNULL stdin (fail fast
    on an unexpected prompt instead of hanging), its own session, and an
    enlarged StreamReader limit (one very long output line must not raise).
    """
    mock_subprocess.return_value = create_mock_process(returncode=0)
    await list_worktrees()

    _, kwargs = mock_subprocess.call_args
    assert kwargs["stdin"] == asyncio.subprocess.DEVNULL
    assert kwargs["start_new_session"] is True
    assert kwargs["limit"] == 8 * 1024 * 1024
