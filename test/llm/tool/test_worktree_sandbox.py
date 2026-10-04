"""The worktree tools under a sandbox policy: every git call is wrapped, and
the model cannot steer what the tools write."""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.sandbox import SandboxPolicy
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
            side_effect=lambda argv, policy, skip=False: (argv, None),
        ) as mock_build:
            await enter_worktree(branch_name="test-branch", cwd=tmpdir)

        argvs = [call.args[0] for call in mock_build.call_args_list]
        assert argvs == [
            ["git", "rev-parse", "--show-toplevel"],
            [
                "git",
                "worktree",
                "add",
                "-b",
                "test-branch",
                os.path.join(tmpdir, ".zrb", "worktree", "test-branch"),
            ],
        ]


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
            side_effect=lambda argv, policy, skip=False: (argv, None),
        ) as mock_build:
            await exit_worktree(tmpdir)

        argvs = [call.args[0] for call in mock_build.call_args_list]
        assert argvs[0][:2] == ["git", "-C"]
        assert argvs[1] == ["git", "worktree", "remove", "--force", tmpdir]
        assert argvs[2] == ["git", "branch", "-D", "test-branch"]


@pytest.mark.asyncio
async def test_enter_worktree_refuses_a_repo_outside_the_sandbox(
    mock_subprocess, monkeypatch
):
    """`cwd` is the model's choice; naming another repo must not let it write there."""
    with (
        tempfile.TemporaryDirectory() as project,
        tempfile.TemporaryDirectory(dir=os.path.expanduser("~")) as other_repo,
    ):
        monkeypatch.setattr(
            "zrb.llm.tool.worktree.get_effective_sandbox_policy",
            lambda: SandboxPolicy(enabled=True, writable_paths=(project,)),
        )
        mock_subprocess.side_effect = [
            create_mock_process(returncode=0, stdout=other_repo.encode()),
        ]
        res = await enter_worktree(branch_name="escape", cwd=other_repo)

        assert "Blocked by sandbox policy" in res
        assert not os.path.exists(os.path.join(other_repo, ".zrb"))
        assert mock_subprocess.call_count == 1  # no `git worktree add`


@pytest.mark.asyncio
async def test_enter_worktree_refuses_a_branch_name_that_leaves_the_sandbox(
    mock_subprocess, monkeypatch
):
    """`branch_name` becomes a path; climbing out with `..` must be refused."""
    with tempfile.TemporaryDirectory(dir=os.path.expanduser("~")) as project:
        monkeypatch.setattr(
            "zrb.llm.tool.worktree.get_effective_sandbox_policy",
            lambda: SandboxPolicy(enabled=True, writable_paths=(project,)),
        )
        mock_subprocess.side_effect = [
            create_mock_process(returncode=0, stdout=project.encode()),
        ]
        res = await enter_worktree(branch_name="../../../escape", cwd=project)

        assert "Blocked by sandbox policy" in res
        assert mock_subprocess.call_count == 1  # no `git worktree add`


@pytest.mark.asyncio
async def test_list_worktrees_routes_git_calls_through_sandbox(mock_subprocess):
    mock_subprocess.return_value = create_mock_process(returncode=0, stdout=b"")
    with patch(
        "zrb.llm.tool.worktree.build_sandboxed_argv",
        side_effect=lambda argv, policy, skip=False: (argv, None),
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
        side_effect=lambda argv, policy, skip=False: (
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

        def fake_build(argv, policy, skip=False):
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

        def fake_build(argv, policy, skip=False):
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
