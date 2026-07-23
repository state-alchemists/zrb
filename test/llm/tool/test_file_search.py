import os
from unittest.mock import MagicMock, patch

from zrb.llm.tool import file_search as file_search_mod
from zrb.llm.tool.file_search import search_files


def _no_ripgrep():
    """Force the os.walk fallback by making ripgrep look unavailable."""
    return patch("zrb.llm.tool.file_search.shutil.which", return_value=None)


def test_os_walk_skips_hidden_excluded_and_nonmatching(tmp_path):
    # Arrange: one file per skip branch plus one that should match.
    (tmp_path / ".secret").write_text("needle here\n")  # hidden -> skipped
    (tmp_path / "skip.log").write_text("needle here\n")  # excluded pattern
    (tmp_path / "note.txt").write_text("needle here\n")  # file_pattern mismatch
    (tmp_path / "keep.py").write_text("needle here\n")  # matches

    # Act
    with _no_ripgrep():
        result = search_files(
            "needle",
            path=str(tmp_path),
            file_pattern="*.py",
            exclude_patterns=["*.log"],
        )

    # Assert: only keep.py survives every filter.
    files = [r["file"] for r in result["results"]]
    assert any(f.endswith("keep.py") for f in files)
    assert not any("secret" in f for f in files)
    assert not any("skip.log" in f for f in files)
    assert not any("note.txt" in f for f in files)


def test_os_walk_skips_when_relpath_component_excluded(tmp_path):
    # Arrange: the file itself is fine, but its relative path contains an
    # excluded component ("excludedir"), which the rel-path check must catch.
    sub = tmp_path / "excludedir"
    sub.mkdir()
    (sub / "keep.py").write_text("needle here\n")

    # Act
    with _no_ripgrep():
        result = search_files(
            "needle",
            path=str(sub),
            exclude_patterns=["excludedir"],
        )

    # Assert
    assert "No matches" in result["summary"]


def test_os_walk_timeout_during_file_loop(tmp_path):
    # Arrange: a single matching file, with a fake clock that stays under the
    # timeout for the start + directory checks, then jumps past it inside the
    # per-file loop.
    (tmp_path / "keep.py").write_text("needle here\n")
    calls = {"n": 0}

    def fake_time():
        calls["n"] += 1
        return 0.0 if calls["n"] <= 2 else 100.0

    # Act
    with (
        _no_ripgrep(),
        patch("zrb.llm.tool.file_search.time.time", side_effect=fake_time),
    ):
        result = search_files("needle", path=str(tmp_path), timeout=5)

    # Assert
    assert "warning" in result
    assert "timed out" in result["warning"]


def test_ripgrep_returncode_2_falls_back_to_os_walk(tmp_path):
    # Arrange: ripgrep is "available" but exits with code 2 (fatal error),
    # which must trigger the os.walk fallback that finds the real match.
    (tmp_path / "keep.py").write_text("needle here\n")
    proc = MagicMock(returncode=2, stdout="")

    # Act
    with (
        patch("zrb.llm.tool.file_search.shutil.which", return_value="/usr/bin/rg"),
        patch("zrb.llm.tool.file_search.subprocess.run", return_value=proc),
    ):
        result = search_files("needle", path=str(tmp_path))

    # Assert: fallback found keep.py despite ripgrep failing.
    assert any(r["file"].endswith("keep.py") for r in result["results"])


def test_ripgrep_skips_unreadable_file_and_warns(tmp_path):
    # Arrange: ripgrep reports a file that cannot actually be opened; the
    # extraction step must skip it and surface a warning. files_only exercises
    # the warning/truncation attachment on that output shape.
    proc = MagicMock(returncode=0, stdout="/does/not/exist/ghost.txt\n")

    # Act
    with (
        patch("zrb.llm.tool.file_search.shutil.which", return_value="/usr/bin/rg"),
        patch("zrb.llm.tool.file_search.subprocess.run", return_value=proc),
    ):
        result = search_files("needle", path=str(tmp_path), files_only=True)

    # Assert
    assert result["files"] == []
    assert "warning" in result
    assert "skipped" in result["warning"]


def test_files_only_truncation_notice(tmp_path):
    # Arrange: several matching files with a tiny output budget so head-keep
    # truncation kicks in and attaches a notice to the files_only output.
    for i in range(6):
        (tmp_path / f"match_file_{i}.py").write_text("needle here\n")

    # Act
    with _no_ripgrep(), patch("zrb.llm.tool.file_search.CFG") as mock_cfg:
        mock_cfg.LLM_MAX_OUTPUT_CHARS = 10
        result = search_files("needle", path=str(tmp_path), files_only=True)

    # Assert
    assert "truncation_notice" in result
    assert "TRUNCATED" in result["truncation_notice"]
    assert 0 < len(result["files"]) < 6


def test_os_walk_skips_unreadable_file(tmp_path):
    # Arrange: a file that os.walk lists but _get_file_matches cannot read, so
    # the walk must skip it with a warning. Uses a mock instead of chmod so the
    # test works regardless of whether it runs as root (GitLab CI containers).
    locked = tmp_path / "locked.py"
    locked.write_text("needle here\n")
    real_get_file_matches = file_search_mod._get_file_matches

    def _raising_get_file_matches(file_path, *args, **kwargs):
        if str(file_path).endswith("locked.py"):
            raise OSError("Permission denied")
        return real_get_file_matches(file_path, *args, **kwargs)

    # Act
    with (
        _no_ripgrep(),
        patch(
            "zrb.llm.tool.file_search._get_file_matches",
            side_effect=_raising_get_file_matches,
        ),
    ):
        result = search_files("needle", path=str(tmp_path))

    # Assert
    assert "warning" in result
    assert "skipped" in result["warning"]
