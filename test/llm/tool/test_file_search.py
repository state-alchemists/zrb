from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.tool import file_search as file_search_mod
from zrb.llm.tool.file import search_files
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
    # Arrange: a file that os.walk lists but get_file_matches cannot read, so
    # the walk must skip it with a warning. Uses a mock instead of chmod so the
    # test works regardless of whether it runs as root (GitLab CI containers).
    locked = tmp_path / "locked.py"
    locked.write_text("needle here\n")
    real_get_file_matches = file_search_mod.get_file_matches

    def _raising_get_file_matches(file_path, *args, **kwargs):
        if str(file_path).endswith("locked.py"):
            raise OSError("Permission denied")
        return real_get_file_matches(file_path, *args, **kwargs)

    # Act
    with (
        _no_ripgrep(),
        patch(
            "zrb.llm.tool.file_search.get_file_matches",
            side_effect=_raising_get_file_matches,
        ),
    ):
        result = search_files("needle", path=str(tmp_path))

    # Assert
    assert "warning" in result
    assert "skipped" in result["warning"]


def test_search_files_invalid_regex(tmp_path):
    result = search_files("[invalid(regex", path=str(tmp_path))
    assert "error" in result
    assert "Invalid regex" in result["error"]


def test_search_files_nonexistent_path():
    result = search_files("pattern", path="/nonexistent/path/xyz")
    assert "error" in result
    assert "not found" in result["error"].lower()


def test_search_files_timeout(tmp_path):
    # timeout=0 means any iteration will exceed it immediately
    file_path = tmp_path / "test.txt"
    file_path.write_text("hello world\nzrb is here")

    result = search_files("hello", path=str(tmp_path), timeout=0)
    # Should have a warning about timing out
    assert "warning" in result


def test_search_files_file_pattern(tmp_path):
    (tmp_path / "match.py").write_text("target pattern here")
    (tmp_path / "skip.txt").write_text("target pattern here")

    result = search_files("target", path=str(tmp_path), file_pattern="*.py")
    matched_files = [r["file"] for r in result.get("results", [])]
    assert any("match.py" in f for f in matched_files)
    assert not any("skip.txt" in f for f in matched_files)


def test_search_files_no_matches(tmp_path):
    (tmp_path / "file.txt").write_text("nothing relevant here")

    result = search_files("zzz_no_match_pattern", path=str(tmp_path))
    assert "No matches found" in result.get("summary", "")


def test_search_files_result_truncation(tmp_path):
    # Create more than 500 files each containing the search pattern
    for i in range(600):
        (tmp_path / f"file_{i:04d}.txt").write_text("needle")

    result = search_files("needle", path=str(tmp_path))
    assert "truncation_notice" in result
    assert 0 < len(result["results"]) < 600


def test_search_files_files_only(tmp_path):
    (tmp_path / "match1.py").write_text("import os\nfoo = 1")
    (tmp_path / "match2.py").write_text("foo = 2")
    (tmp_path / "nomatch.py").write_text("bar = 3")

    result = search_files("foo", path=str(tmp_path), files_only=True)
    assert "files" in result
    assert "results" not in result
    files = result["files"]
    assert len(files) == 2
    assert all(isinstance(f, str) for f in files)
    assert any("match1.py" in f for f in files)
    assert any("match2.py" in f for f in files)
    assert not any("nomatch.py" in f for f in files)


def test_search_files_case_insensitive(tmp_path):
    (tmp_path / "file.txt").write_text("Hello World\nfoo bar")

    result_sensitive = search_files("hello", path=str(tmp_path), case_sensitive=True)
    assert "No matches found" in result_sensitive.get("summary", "")

    result_insensitive = search_files("hello", path=str(tmp_path), case_sensitive=False)
    assert "Found 1 matches" in result_insensitive.get("summary", "")


def test_search_files_context_lines(tmp_path):
    content = "\n".join(f"line{i}" for i in range(10))
    (tmp_path / "file.txt").write_text(content)

    # context_lines=0: no surrounding lines
    result_no_ctx = search_files("line5", path=str(tmp_path), context_lines=0)
    match = result_no_ctx["results"][0]["matches"][0]
    assert match["context_before"] == []
    assert match["context_after"] == []

    # context_lines=1: one line before and after
    result_ctx = search_files("line5", path=str(tmp_path), context_lines=1)
    match = result_ctx["results"][0]["matches"][0]
    assert len(match["context_before"]) == 1
    assert len(match["context_after"]) == 1


def test_search_files_files_only_summary(tmp_path):
    (tmp_path / "a.txt").write_text("target")
    (tmp_path / "b.txt").write_text("target")

    result = search_files("target", path=str(tmp_path), files_only=True)
    assert "Found" in result.get("summary", "")
    assert "2 files" in result.get("summary", "")


class TestSearchFilesFallback:
    @pytest.fixture
    def temp_search_dir(self, tmp_path):
        d = tmp_path / "test_search_fallback"
        d.mkdir()
        (d / "file1.txt").write_text(
            "hello world\nline 2\nline 3\nline 4\nline 5\nline 6"
        )
        (d / "file2.py").write_text("print('hello')\n# comment")
        return str(d)

    def test_search_files_python_fallback(self, temp_search_dir):
        from unittest.mock import patch

        # Mock shutil.which to pretend 'rg' is not installed
        with patch("shutil.which", return_value=None):
            result = search_files("hello", path=temp_search_dir)

            assert "Found 2 matches in 2 files" in result["summary"]
            assert len(result["results"]) == 2
            # Check if it actually used the Python fallback
            assert "(searched" in result["summary"]

    def test_search_files_python_fallback_files_only(self, temp_search_dir):
        from unittest.mock import patch

        with patch("shutil.which", return_value=None):
            result = search_files("hello", path=temp_search_dir, files_only=True)

            assert "files" in result
            assert len(result["files"]) == 2

    def test_search_files_python_fallback_no_match(self, temp_search_dir):
        from unittest.mock import patch

        with patch("shutil.which", return_value=None):
            result = search_files("nonexistent_pattern_xyz", path=temp_search_dir)
            assert "No matches found" in result["summary"]

    def test_search_files_python_fallback_timeout(self, temp_search_dir):
        from unittest.mock import patch

        with (
            patch("shutil.which", return_value=None),
            patch("time.time", side_effect=[0, 100]),
        ):  # Fake immediate timeout
            result = search_files("hello", path=temp_search_dir, timeout=0.1)
            assert "warning" in result
            assert "timed out" in result["warning"]


class TestFileSearchTruncation:
    def test_get_file_matches_truncation(self, tmp_path):
        # Tested via the public search_files: a file with more matches than the
        # per-file cap gets a head-keep truncation marker.
        file_path = tmp_path / "large_file.txt"
        file_path.write_text("\n".join([f"match {i}" for i in range(100)]))

        from unittest.mock import patch

        with (
            patch("zrb.llm.tool.file_search.MAX_MATCHES_PER_FILE", 20),
            patch("shutil.which", return_value=None),
        ):
            result = search_files("match", path=str(tmp_path))
            # The result for this one file should have truncation marker
            assert any(
                "TRUNCATED" in m["line_content"]
                for r in result["results"]
                for m in r["matches"]
            )

    def test_search_files_python_fallback_truncation(self, tmp_path):
        from unittest.mock import patch

        with (
            patch("shutil.which", return_value=None),
            patch("zrb.llm.tool.file_search.CFG") as mock_cfg,
        ):

            # Create many matching files
            for i in range(20):
                (tmp_path / f"match_{i}.txt").write_text("needle")

            # Tiny char budget so the result-file list overflows and truncates.
            mock_cfg.LLM_MAX_OUTPUT_CHARS = 100

            result = search_files("needle", path=str(tmp_path))
            assert "truncation_notice" in result
            assert "TRUNCATED" in result["truncation_notice"]
