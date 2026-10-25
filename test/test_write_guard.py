"""The suite writes inside temp only: the home redirect and the write guard."""

import os
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


def test_rename_is_judged_by_its_destination(guard, tmp_path):
    guard.audit(
        "os.rename", (str(tmp_path / "repo" / "a"), str(tmp_path / "elsewhere"))
    )

    with pytest.raises(PermissionError):
        guard.audit(
            "os.rename", (str(tmp_path / "elsewhere"), str(tmp_path / "repo" / "b"))
        )


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
    guard.audit("os.remove", ("/anything",))

    assert guard.violations == []


def test_relative_low_level_open_is_not_judged(guard):
    """`os.open(name, dir_fd=fd)` names the directory outside the event."""
    flags = os.O_WRONLY | os.O_CREAT

    guard.audit("open", ("entry.png", None, flags))

    assert guard.violations == []
