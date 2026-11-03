"""The worktree tools under a sandbox policy: every git call is wrapped, and
the model cannot steer what the tools write."""

import hashlib
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.sandbox import SandboxPolicy
from zrb.llm.sandbox.os_sandbox import SandboxUnavailableError
from zrb.llm.tool import worktree
from zrb.llm.tool.worktree import enter_worktree, exit_worktree, list_worktrees


def _expected_worktree_path(repo: str, branch: str) -> str:
    """The documented layout — ``<worktree dir>/<repo>-<digest>/<branch>``."""
    real_repo = os.path.realpath(repo)
    digest = hashlib.sha256(real_repo.encode("utf-8")).hexdigest()[:8]
    return os.path.join(
        os.path.realpath(os.path.expanduser("~")),
        ".zrb",
        "wt",
        f"{os.path.basename(real_repo)}-{digest}",
        branch,
    )


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch):
    """Worktrees land under ~/.zrb/wt: never write into the developer's home."""
    with tempfile.TemporaryDirectory() as home:
        monkeypatch.setenv("HOME", home)
        yield home


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
    """worktree git subprocesses go through the OS-level sandbox `Shell` uses (ADR-0065)."""
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
                _expected_worktree_path(tmpdir, "test-branch"),
            ],
        ]


@pytest.mark.asyncio
async def test_a_read_only_repository_names_both_writable_paths(
    mock_subprocess, monkeypatch, outside_root
):
    """git records the branch inside the repository, so the worktree root alone is not enough.

    A sandbox list that names the worktree root *instead of* the project used to
    fail later, with git's own "Operation not permitted" on a `.git` lock. The
    repository is judged before git runs, and the message names both roots.
    """
    repo = str(outside_root / "repo")  # a path to judge, never created
    worktree_home = str(outside_root / "wt")
    monkeypatch.setattr(
        "zrb.llm.tool.worktree.get_effective_sandbox_policy",
        lambda: SandboxPolicy(enabled=True, writable_paths=(worktree_home,)),
    )
    monkeypatch.setattr(worktree, "_worktree_root", lambda: worktree_home)
    mock_subprocess.side_effect = [
        create_mock_process(returncode=0, stdout=repo.encode()),
    ]

    res = await enter_worktree(branch_name="b", cwd=repo)

    assert "Blocked by sandbox policy" in res
    assert "LLM_SANDBOX_WRITABLE_PATHS" in res
    assert repo in res
    assert worktree_home in res
    assert mock_subprocess.call_count == 1  # the probe; nothing was written


@pytest.mark.asyncio
async def test_a_repository_outside_the_writable_roots_is_refused(
    mock_subprocess, monkeypatch, outside_root
):
    """`cwd` names a directory; the repository root git resolves it to is written.

    That root can be an ancestor outside the writable set, so the destination
    alone being writable must not let `git worktree add` touch another
    repository's `.git`.
    """
    project = str(outside_root / "project")  # a path to judge, never created
    repo = str(outside_root / "projectB")
    monkeypatch.setattr(
        worktree,
        "get_effective_sandbox_policy",
        lambda: SandboxPolicy(enabled=True, writable_paths=(project,)),
    )
    mock_subprocess.side_effect = [
        create_mock_process(returncode=0, stdout=repo.encode()),
        create_mock_process(returncode=0),  # what an unjudged `add` would run
    ]

    res = await enter_worktree(branch_name="x", cwd=repo)

    assert "Blocked by sandbox policy" in res
    assert "git worktree add" not in res
    assert mock_subprocess.call_count == 1  # no `git worktree add`


@pytest.mark.asyncio
async def test_a_writable_repository_still_creates_a_worktree(
    mock_subprocess, monkeypatch, tmp_path
):
    """The new check is the repository's boundary, not a second destination check."""
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(
        worktree,
        "get_effective_sandbox_policy",
        lambda: SandboxPolicy(enabled=True, writable_paths=(str(repo),)),
    )
    monkeypatch.setattr(worktree, "_worktree_parent", lambda _root: str(repo / "wt"))
    mock_subprocess.side_effect = [
        create_mock_process(returncode=0, stdout=str(repo).encode()),
        create_mock_process(returncode=0),
    ]

    res = await enter_worktree(branch_name="ok", cwd=str(repo))

    assert "Worktree created:" in res


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
async def test_enter_worktree_refuses_a_destination_outside_the_sandbox(
    mock_subprocess, monkeypatch, outside_root
):
    """The worktree home is the write target now, so it is what the sandbox judges.

    `cwd` is the model's choice; naming another repo's worktree home must not let
    it write there. The repository itself is never written to, so nothing appears
    in it either.
    """
    other_repo = str(outside_root / "other-repo")  # a path to judge, never created
    project = str(outside_root / "project")
    with tempfile.TemporaryDirectory() as repo:
        monkeypatch.setattr(
            "zrb.llm.tool.worktree.get_effective_sandbox_policy",
            lambda: SandboxPolicy(enabled=True, writable_paths=(project,)),
        )
        monkeypatch.setattr(
            worktree, "_worktree_parent", lambda _root: str(outside_root / "wt")
        )
        mock_subprocess.side_effect = [
            create_mock_process(returncode=0, stdout=repo.encode()),
        ]
        res = await enter_worktree(branch_name="escape", cwd=repo)

        assert "Blocked by sandbox policy" in res
        assert not os.path.exists(os.path.join(repo, ".zrb"))
        assert mock_subprocess.call_count == 1  # no `git worktree add`


@pytest.mark.asyncio
async def test_enter_worktree_refuses_a_branch_name_that_leaves_the_sandbox(
    mock_subprocess, monkeypatch, outside_root
):
    """`branch_name` becomes a path; climbing out with `..` must be refused."""
    project = str(outside_root / "project")  # a path to judge, never created
    monkeypatch.setattr(
        "zrb.llm.tool.worktree.get_effective_sandbox_policy",
        lambda: SandboxPolicy(enabled=True, writable_paths=(project,)),
    )
    monkeypatch.setattr(worktree, "_worktree_parent", lambda _root: project)
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
    """A successful removal is still reported when the branch delete hits
    SandboxUnavailableError."""
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
    """A first-call sandbox-fallback warning survives a later call's failure."""
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
