"""The suite writes inside temp only: the home redirect and the write guard."""

import os
import shutil
import sys
import tempfile

import pytest
from write_guard import WriteGuard


@pytest.fixture
def guard(tmp_path):
    (tmp_path / "home" / "tmp").mkdir(parents=True)
    (tmp_path / "repo").mkdir()
    return WriteGuard(
        forbidden_roots=[str(tmp_path / "home"), str(tmp_path / "repo")],
        allowed_roots=[str(tmp_path / "home" / "tmp")],
    )


def test_suite_home_is_redirected_into_temp():
    home = os.path.realpath(os.path.expanduser("~"))
    temp = os.path.realpath(tempfile.gettempdir())

    assert os.path.commonpath([home, temp]) == temp


def test_write_to_the_real_home_is_refused(guard, tmp_path):
    target = tmp_path / "home" / ".zrb" / "session" / "x.json"

    with pytest.raises(PermissionError, match="may only write inside temp"):
        guard.audit("open", (str(target), "w", 0))

    assert guard.violations == [os.path.normcase(os.path.realpath(target))]


def test_write_into_the_repository_is_refused(guard, tmp_path):
    target = tmp_path / "repo" / "test" / "test-generated-basic"

    with pytest.raises(PermissionError):
        guard.audit("os.mkdir", (str(target), 0o777, -1))


@pytest.mark.parametrize("mode", ["r", "rb"])
def test_read_is_not_a_write(guard, tmp_path, mode):
    guard.audit("open", (str(tmp_path / "repo" / "a.py"), mode, 0))

    assert guard.violations == []


def test_low_level_open_for_writing_is_refused(guard, tmp_path):
    flags = os.O_WRONLY | os.O_CREAT

    with pytest.raises(PermissionError):
        guard.audit("open", (str(tmp_path / "repo" / "a.txt"), None, flags))


def test_rename_into_the_repository_is_refused(guard, tmp_path):
    with pytest.raises(PermissionError):
        guard.audit(
            "os.rename",
            (str(tmp_path / "elsewhere"), str(tmp_path / "repo" / "b"), -1, -1),
        )


def test_rename_out_of_the_repository_is_refused(guard, tmp_path):
    with pytest.raises(PermissionError):
        guard.audit(
            "os.rename",
            (str(tmp_path / "repo" / "a.py"), str(tmp_path / "elsewhere"), -1, -1),
        )


def test_rename_inside_temp_is_allowed(guard, tmp_path):
    temp = tmp_path / "home" / "tmp"

    guard.audit("os.rename", (str(temp / "a"), str(temp / "b"), -1, -1))

    assert guard.violations == []


@pytest.mark.parametrize("event", ["os.remove", "os.rmdir"])
def test_deleting_from_the_repository_is_refused(guard, tmp_path, event):
    with pytest.raises(PermissionError):
        guard.audit(event, (str(tmp_path / "repo" / "src" / "x.py"), -1))


def test_deleting_inside_temp_and_artifacts_is_allowed(guard, tmp_path):
    guard.audit("os.remove", (str(tmp_path / "home" / "tmp" / "x"), -1))
    guard.audit("os.remove", (str(tmp_path / "repo" / "__pycache__" / "x.pyc"), -1))

    assert guard.violations == []


def test_real_rmtree_of_a_temp_tree_is_not_refused(tmp_path):
    tree = tmp_path / "tree" / "deep"
    tree.mkdir(parents=True)
    (tree / "f.txt").write_text("x")

    shutil.rmtree(tmp_path / "tree")

    assert not (tmp_path / "tree").exists()


def test_relative_write_is_judged_against_the_cwd(guard, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path / "repo")

    with pytest.raises(PermissionError):
        guard.audit("open", ("leak.txt", "w", 0))


def test_relative_write_in_a_temp_cwd_is_allowed(guard, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path / "home" / "tmp")

    guard.audit("open", ("fine.txt", "w", 0))

    assert guard.violations == []


needs_directory_descriptors = pytest.mark.skipif(
    sys.platform not in ("linux", "darwin"), reason="traces a descriptor to its path"
)


@needs_directory_descriptors
def test_mkdir_through_a_repository_descriptor_is_refused(guard, tmp_path):
    fd = os.open(tmp_path / "repo", os.O_RDONLY)
    try:
        with pytest.raises(PermissionError):
            guard.audit("os.mkdir", ("sub", 0o777, fd))
    finally:
        os.close(fd)


@needs_directory_descriptors
def test_mkdir_through_a_temp_descriptor_is_allowed(guard, tmp_path):
    fd = os.open(tmp_path / "home" / "tmp", os.O_RDONLY)
    try:
        guard.audit("os.mkdir", ("sub", 0o777, fd))
    finally:
        os.close(fd)

    assert guard.violations == []


def test_an_untraceable_descriptor_fails_closed(guard):
    read_end, write_end = os.pipe()
    os.close(read_end)
    os.close(write_end)

    with pytest.raises(PermissionError, match="cannot be traced"):
        guard.audit("os.mkdir", ("sub", 0o777, read_end))


def test_write_inside_an_allowed_root_nested_in_a_forbidden_one_passes(guard, tmp_path):
    guard.audit("open", (str(tmp_path / "home" / "tmp" / "f.txt"), "w", 0))

    assert guard.violations == []


@pytest.mark.parametrize(
    "relative",
    [
        "src/zrb/__pycache__/x.cpython-314.pyc",
        ".coverage.host.123",
        "htmlcov/index.html",
        ".pytest_cache/v/cache/lastfailed",
        "README.pypi.md",
    ],
)
def test_tool_artifacts_in_the_repository_are_not_leaks(guard, tmp_path, relative):
    guard.audit("open", (str(tmp_path / "repo" / relative), "w", 0))

    assert guard.violations == []


def test_file_descriptors_and_other_events_are_ignored(guard):
    guard.audit("open", (3, "w", 0))
    guard.audit("os.chmod", ("/anything", 0o644))

    assert guard.violations == []


def test_relative_low_level_open_is_not_judged(guard):
    """`os.open(name, dir_fd=fd)` names the directory outside the event."""
    flags = os.O_WRONLY | os.O_CREAT

    guard.audit("open", ("entry.png", None, flags))

    assert guard.violations == []


def _symlink_or_skip(link, target):
    try:
        os.symlink(target, link)
    except OSError as error:  # Windows needs a privilege to create one
        pytest.skip(f"cannot create a symlink on this platform: {error}")


def test_a_repository_symlink_to_temp_cannot_be_unlinked(guard, tmp_path):
    link = tmp_path / "repo" / "repo-link"
    _symlink_or_skip(link, tmp_path / "home" / "tmp")

    with pytest.raises(PermissionError):
        guard.audit("os.remove", (str(link), -1))


def test_a_repository_symlink_to_temp_cannot_be_renamed_away(guard, tmp_path):
    link = tmp_path / "repo" / "repo-link"
    _symlink_or_skip(link, tmp_path / "home" / "tmp")

    with pytest.raises(PermissionError):
        guard.audit("os.rename", (str(link), str(tmp_path / "moved"), -1, -1))


def test_a_temp_symlink_to_the_repository_can_be_unlinked(guard, tmp_path):
    link = tmp_path / "home" / "tmp" / "to-repo"
    _symlink_or_skip(link, tmp_path / "repo")

    guard.audit("os.remove", (str(link), -1))

    assert guard.violations == []


def test_writing_through_a_temp_symlink_to_the_repository_is_refused(guard, tmp_path):
    link = tmp_path / "home" / "tmp" / "to-repo"
    _symlink_or_skip(link, tmp_path / "repo")

    with pytest.raises(PermissionError):
        guard.audit("open", (str(link / "f.txt"), "w", 0))


def test_truncating_a_repository_file_is_refused(guard, tmp_path):
    with pytest.raises(PermissionError):
        guard.audit("os.truncate", (str(tmp_path / "repo" / "a.py"), 0))


def test_truncating_a_temp_file_and_a_descriptor_is_not_refused(guard, tmp_path):
    guard.audit("os.truncate", (str(tmp_path / "home" / "tmp" / "f"), 0))
    guard.audit("os.truncate", (5, 0))  # `os.ftruncate`: no path to judge

    assert guard.violations == []
