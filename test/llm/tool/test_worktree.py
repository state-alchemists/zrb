import asyncio
import hashlib
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.shared.ambient_state import get_active_worktree
from zrb.llm.prompt.live_context import render_live_context
from zrb.llm.tool.delegate.worktree import enter_worktree, exit_worktree, list_worktrees


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
    """Worktrees land under ~/.zrb/wt: never write into the developer's home.

    Deliberately not `tmp_path`: the home has to sit outside the directory a test
    uses as its repository, or "created outside the checkout" cannot be asserted.
    """
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
async def test_enter_worktree_success(mock_subprocess, tmp_path):
    mock_subprocess.side_effect = [
        create_mock_process(  # the repo root
            returncode=0, stdout=str(tmp_path).encode()
        ),
        create_mock_process(
            returncode=0, stdout=b"Preparing worktree", stderr=b""
        ),  # git worktree add
    ]

    res = await enter_worktree(branch_name="test-branch")
    assert "Worktree created:" in res
    assert "Branch: test-branch" in res
    # Outside the checkout, under the user's zrb directory: a worktree nested in
    # the repo is a second copy of the repo that every search then has to skip.
    expected = _expected_worktree_path(str(tmp_path), "test-branch")
    assert expected in res
    assert not expected.startswith(str(tmp_path) + os.sep)


@pytest.mark.asyncio
async def test_worktree_root_follows_the_setting(
    mock_subprocess, tmp_path, monkeypatch
):
    """The root is `LLM_WORKTREE_DIR`, not a path baked into the tool."""
    custom_root = tmp_path / "worktrees"
    monkeypatch.setenv("ZRB_LLM_WORKTREE_DIR", str(custom_root))
    repo = tmp_path / "repo"
    repo.mkdir()
    mock_subprocess.side_effect = [
        create_mock_process(returncode=0, stdout=str(repo).encode()),
        create_mock_process(returncode=0),
    ]

    res = await enter_worktree(branch_name="test-branch", cwd=str(repo))

    assert str(custom_root) in res


@pytest.mark.asyncio
async def test_a_relative_worktree_root_is_absolute_when_git_sees_it(
    mock_subprocess, tmp_path, monkeypatch
):
    """git resolves a relative destination against its own cwd, not the process one.

    The sandbox check and `os.makedirs` use the process directory, so a
    relative `LLM_WORKTREE_DIR` has to be made absolute first; otherwise the
    repository can receive a worktree at a path nothing judged.
    """
    process_dir = tmp_path / "process"
    process_dir.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(process_dir)
    monkeypatch.setenv("ZRB_LLM_WORKTREE_DIR", "worktrees")
    mock_subprocess.side_effect = [
        create_mock_process(returncode=0, stdout=str(repo).encode()),
        create_mock_process(returncode=0),
    ]

    with patch(
        "zrb.llm.tool.delegate.worktree.build_sandboxed_argv",
        side_effect=lambda argv, policy, skip=False: (argv, None),
    ) as mock_build:
        res = await enter_worktree(branch_name="test-branch", cwd=str(repo))

    target = mock_build.call_args_list[1].args[0][-1]
    assert os.path.isabs(target)
    assert os.path.realpath(target).startswith(
        os.path.realpath(str(process_dir / "worktrees"))
    )
    assert not os.path.exists(os.path.join(repo, "worktrees"))
    assert "Worktree created:" in res


@pytest.mark.asyncio
async def test_two_repositories_sharing_a_name_get_their_own_dir(tmp_path):
    """`api` in two different places is two repositories, not one shared path."""
    parents = [tmp_path / "client-a", tmp_path / "client-b"]
    repos = [parent / "api" for parent in parents]
    for repo in repos:
        repo.mkdir(parents=True)
    created: list[str] = []
    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_subprocess.side_effect = [
            create_mock_process(returncode=0, stdout=str(repos[0]).encode()),
            create_mock_process(returncode=0),
            create_mock_process(returncode=0, stdout=str(repos[1]).encode()),
            create_mock_process(returncode=0),
        ]
        for repo in repos:
            res = await enter_worktree(branch_name="same-branch", cwd=str(repo))
            created.append(res.split("Worktree created: ")[1].splitlines()[0])

    assert created[0] != created[1]
    assert os.path.dirname(created[0]) != os.path.dirname(created[1])


@pytest.mark.asyncio
async def test_enter_worktree_does_not_touch_the_repository(mock_subprocess, tmp_path):
    """Nothing is written into the checkout — not even a .gitignore entry.

    The old layout needed one because the worktree lived inside the repo; the
    new one lives outside it, so the repository stays exactly as it was.
    """
    before = sorted(os.listdir(tmp_path))
    mock_subprocess.side_effect = [
        create_mock_process(returncode=0, stdout=str(tmp_path).encode()),
        create_mock_process(returncode=0),
    ]
    await enter_worktree(branch_name="clean-branch", cwd=str(tmp_path))

    assert sorted(os.listdir(tmp_path)) == before
    assert not os.path.exists(os.path.join(tmp_path, ".gitignore"))


@pytest.mark.asyncio
async def test_enter_worktree_no_branch_name(mock_subprocess, tmp_path):
    mock_subprocess.side_effect = [
        create_mock_process(  # the repo root; the tool creates .zrb/worktree in it
            returncode=0, stdout=str(tmp_path).encode()
        ),
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
async def test_enter_worktree_resumes_existing_linked_worktree(mock_subprocess):
    with tempfile.TemporaryDirectory() as tmpdir:
        canonical_worktree_path = os.path.join(tmpdir, ".zrb", "worktree", "existing")
        worktree_path = os.path.join(
            tmpdir, ".zrb", "worktree", "existing", "..", "existing"
        )
        os.makedirs(canonical_worktree_path)
        mock_subprocess.side_effect = [
            create_mock_process(returncode=0, stdout=f"{tmpdir}\n".encode()),
            create_mock_process(
                returncode=0,
                stdout=(
                    f"worktree {tmpdir}\n"
                    "HEAD 1111111\n"
                    "branch refs/heads/main\n\n"
                    f"worktree {canonical_worktree_path}\n"
                    "HEAD 2222222\n"
                    "branch refs/heads/existing\n"
                ).encode(),
            ),
        ]

        res = await enter_worktree(worktree_path=worktree_path, cwd=tmpdir)

        assert f"Worktree resumed: {worktree_path}" in res
        assert f"Worktree resumed: {canonical_worktree_path}\n" not in res
        assert "Branch: existing" in res
        assert get_active_worktree() == os.path.realpath(canonical_worktree_path)
        assert mock_subprocess.call_count == 2


@pytest.mark.asyncio
async def test_enter_worktree_rejects_unregistered_existing_path(mock_subprocess):
    with tempfile.TemporaryDirectory() as tmpdir:
        worktree_path = os.path.join(tmpdir, "existing")
        os.makedirs(worktree_path)
        mock_subprocess.side_effect = [
            create_mock_process(returncode=0, stdout=f"{tmpdir}\n".encode()),
            create_mock_process(
                returncode=0,
                stdout=f"worktree {tmpdir}\nHEAD 1111111\nbranch refs/heads/main\n".encode(),
            ),
        ]

        res = await enter_worktree(worktree_path=worktree_path, cwd=tmpdir)

        assert "Error: Existing worktree was not found" in res
        assert "ListWorktrees" in res


@pytest.mark.asyncio
async def test_enter_worktree_rejects_main_worktree(mock_subprocess):
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_subprocess.side_effect = [
            create_mock_process(returncode=0, stdout=f"{tmpdir}\n".encode()),
            create_mock_process(
                returncode=0,
                stdout=f"worktree {tmpdir}\nHEAD 1111111\nbranch refs/heads/main\n".encode(),
            ),
        ]

        res = await enter_worktree(worktree_path=tmpdir, cwd=tmpdir)

        assert "main working tree" in res
        assert "linked worktree" in res


@pytest.mark.asyncio
async def test_enter_worktree_rejects_main_worktree_from_a_linked_worktree(
    mock_subprocess,
):
    with tempfile.TemporaryDirectory() as tmpdir:
        linked_path = os.path.join(tmpdir, "linked")
        os.makedirs(linked_path)
        mock_subprocess.side_effect = [
            create_mock_process(returncode=0, stdout=f"{linked_path}\n".encode()),
            create_mock_process(
                returncode=0,
                stdout=(
                    f"worktree {tmpdir}\n"
                    "HEAD 1111111\n"
                    "branch refs/heads/main\n\n"
                    f"worktree {linked_path}\n"
                    "HEAD 2222222\n"
                    "branch refs/heads/linked\n"
                ).encode(),
            ),
        ]

        res = await enter_worktree(worktree_path=tmpdir, cwd=linked_path)

        assert "main working tree" in res
        assert "linked worktree" in res


@pytest.mark.asyncio
async def test_enter_worktree_does_not_combine_existing_path_and_new_branch(
    mock_subprocess,
):
    with tempfile.TemporaryDirectory() as tmpdir:
        res = await enter_worktree(
            branch_name="new-branch", worktree_path=os.path.join(tmpdir, "existing")
        )

        assert "branch_name" in res
        assert "worktree_path" in res
        mock_subprocess.assert_not_called()


@pytest.mark.asyncio
async def test_enter_worktree_failure(mock_subprocess, tmp_path):
    mock_subprocess.side_effect = [
        create_mock_process(  # the repo root; the tool creates .zrb/worktree in it
            returncode=0, stdout=str(tmp_path).encode()
        ),
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
    """Unexpected exceptions propagate; the tool wrapper or delegate.py's
    gather handles them (ADR-0057)."""
    mock_subprocess.side_effect = OSError("no such file or directory")

    with pytest.raises(OSError):
        await enter_worktree(branch_name="test-branch")


def _capture_live_context(ctx=None) -> str:
    """Render the live-context block, which carries worktree state."""
    if ctx is None:
        ctx = MagicMock()
        ctx.input.session = "test-session"
    return render_live_context(ctx)


@pytest.mark.asyncio
async def test_enter_and_exit_worktree_reflected_in_live_context(mock_subprocess):
    """EnterWorktree shows active worktree in the live context; ExitWorktree clears it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        worktree_path = _expected_worktree_path(tmpdir, "sc-branch")

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
async def test_run_git_spawns_with_shell_py_style_protections(mock_subprocess):
    """_run_git spawns through shell.py's start_process: DEVNULL stdin (fail fast
    on an unexpected prompt instead of hanging), its own session, and an
    enlarged StreamReader limit (one very long output line must not raise).
    """
    mock_subprocess.return_value = create_mock_process(returncode=0)
    await list_worktrees()

    _, kwargs = mock_subprocess.call_args
    assert kwargs["stdin"] == asyncio.subprocess.DEVNULL
    assert kwargs["start_new_session"] is True
    assert kwargs["limit"] == 8 * 1024 * 1024
