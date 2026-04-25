import os
import shutil

import pytest

from zrb.llm.tool.file import (
    glob_files,
    list_files,
    read_file,
    read_files,
    replace_in_file,
    search_files,
    write_file,
    write_files,
)


@pytest.fixture
def temp_dir(tmp_path):
    d = tmp_path / "test_file_tool"
    d.mkdir()
    return str(d)


def test_write_and_read_file(temp_dir):
    file_path = os.path.join(temp_dir, "test.txt")
    content = "hello world"

    # Test write_file
    res = write_file(file_path, content)
    assert "Successfully wrote to" in res
    assert os.path.exists(file_path)

    # Test read_file
    read_res = read_file(file_path)
    assert content in read_res


def test_list_files(temp_dir):
    os.makedirs(os.path.join(temp_dir, "subdir"))
    with open(os.path.join(temp_dir, "file1.txt"), "w") as f:
        f.write("1")
    with open(os.path.join(temp_dir, "subdir", "file2.txt"), "w") as f:
        f.write("2")

    res = list_files(temp_dir)
    files = res.get("files", [])
    assert "file1.txt" in files
    assert "subdir/file2.txt" in files


def test_glob_files(temp_dir):
    with open(os.path.join(temp_dir, "file1.txt"), "w") as f:
        f.write("1")
    with open(os.path.join(temp_dir, "file2.log"), "w") as f:
        f.write("2")

    res = glob_files("*.txt", path=temp_dir)
    assert isinstance(res, dict)
    files = res.get("files", [])
    assert len(files) == 1
    assert "file1.txt" in files


def test_replace_in_file(temp_dir):
    file_path = os.path.join(temp_dir, "test.txt")
    with open(file_path, "w") as f:
        f.write("hello world")

    res = replace_in_file(file_path, "world", "zrb")
    assert "Successfully updated" in res
    with open(file_path, "r") as f:
        assert f.read() == "hello zrb"


def test_search_files(temp_dir):
    file_path = os.path.join(temp_dir, "test.txt")
    with open(file_path, "w") as f:
        f.write("hello world\nzrb is cool")

    res = search_files("zrb", path=temp_dir)
    assert "Found 1 matches" in res.get("summary", "")
    assert len(res.get("results", [])) == 1
    assert res["results"][0]["file"] == os.path.relpath(file_path, os.getcwd())


# --- list_files additional coverage ---


def test_list_files_nonexistent_path():
    res = list_files("/nonexistent/path/that/does/not/exist")
    assert "error" in res
    assert "does not exist" in res["error"]


def test_list_files_depth_limiting(tmp_path):
    # depth=3 means: root(0), level1(1), level1/level2(2) are walked.
    # At depth 2 (>= depth-1=2), dirs are cleared so level3 is never entered.
    (tmp_path / "level1" / "level2").mkdir(parents=True)
    (tmp_path / "level1" / "level2" / "level1_level2_file.txt").write_text("l2")
    (tmp_path / "level1" / "level2" / "level3").mkdir()
    (tmp_path / "level1" / "level2" / "level3" / "deep_file.txt").write_text("deep")

    res = list_files(str(tmp_path))
    files = res.get("files", [])
    # Files at level1/level2/ (depth 2) should be included
    assert any("level1_level2_file.txt" in f for f in files)
    # Files inside level3 (depth 3) should be excluded due to depth limiting
    assert not any("deep_file.txt" in f for f in files)


def test_list_files_truncation(tmp_path):
    # Create more than 1000 files to trigger truncation
    for i in range(1100):
        (tmp_path / f"file_{i:04d}.txt").write_text("x")

    res = list_files(str(tmp_path))
    assert "truncation_notice" in res
    assert len(res["files"]) == 1000  # 500 head + 500 tail


# --- glob_files additional coverage ---


def test_glob_files_nonexistent_path():
    result = glob_files("*.txt", path="/nonexistent/path/that/does/not/exist")
    assert "error" in result
    assert "does not exist" in result["error"]


def test_glob_files_skips_directories(tmp_path):
    (tmp_path / "mydir.txt").mkdir()
    (tmp_path / "actual.txt").write_text("content")

    res = glob_files("*.txt", path=str(tmp_path))
    files = res.get("files", [])
    assert "actual.txt" in files
    assert "mydir.txt" not in files


def test_glob_files_skips_hidden_path_components(tmp_path):
    hidden_dir = tmp_path / ".hidden"
    hidden_dir.mkdir()
    (hidden_dir / "secret.txt").write_text("secret")
    (tmp_path / "visible.txt").write_text("visible")

    res = glob_files("**/*.txt", path=str(tmp_path))
    files = res.get("files", [])
    assert not any(".hidden" in f for f in files)
    assert any("visible.txt" in f for f in files)


def test_glob_files_excluded_patterns(tmp_path):
    (tmp_path / "keep.txt").write_text("keep")
    (tmp_path / "skip.log").write_text("skip")

    res = glob_files("*", path=str(tmp_path), exclude_patterns=["*.log"])
    files = res.get("files", [])
    assert any("keep.txt" in f for f in files)
    assert not any("skip.log" in f for f in files)


def test_glob_files_truncation(tmp_path):
    for i in range(1100):
        (tmp_path / f"file_{i:04d}.txt").write_text("x")

    res = glob_files("*.txt", path=str(tmp_path))
    assert "truncation_notice" in res
    assert "TRUNCATED" in res["truncation_notice"]
    assert len(res["files"]) == 1000  # 500 head + 500 tail


# --- read_file additional coverage ---


def test_read_file_nonexistent():
    result = read_file("/nonexistent/file/that/does/not/exist.txt")
    assert "Error" in result
    assert "not found" in result.lower() or "File not found" in result


def test_read_file_directory(tmp_path):
    result = read_file(str(tmp_path))
    assert "Error" in result
    assert "directory" in result.lower()


def test_read_file_large_file(tmp_path):
    large_file = tmp_path / "large.txt"
    # Write more than 10MB
    large_file.write_bytes(b"x" * (11 * 1024 * 1024))

    result = read_file(str(large_file))
    assert "Error" in result
    assert "too large" in result.lower()


def test_read_file_binary_with_null_bytes(tmp_path):
    binary_file = tmp_path / "binary.bin"
    binary_file.write_bytes(b"\x00\x01\x02\x03binary data")

    result = read_file(str(binary_file))
    assert "Error" in result
    assert "binary" in result.lower()


def test_read_file_auto_truncate_false(tmp_path):
    file_path = tmp_path / "test.txt"
    content = "line1\nline2\nline3\n"
    file_path.write_text(content)

    result = read_file(str(file_path), auto_truncate=False)
    assert "line1" in result
    assert "line2" in result
    assert "line3" in result
    assert "TRUNCATED" not in result
    assert "IMPORTANT" not in result
    assert "---CONTENT---" in result


def test_read_file_truncation_header(tmp_path):
    file_path = tmp_path / "big.txt"
    line = "x" * 110
    content = "\n".join(line for _ in range(1100))
    file_path.write_text(content)

    result = read_file(str(file_path))
    assert "---CONTENT---" in result
    assert ("[File:" in result and "truncated" in result.lower()) or "File:" in result


def test_read_file_non_utf8(tmp_path):
    file_path = tmp_path / "latin1.txt"
    # Write latin-1 encoded bytes that are not valid UTF-8
    file_path.write_bytes(b"caf\xe9 au lait")

    result = read_file(str(file_path))
    assert "Error" in result
    assert "binary" in result.lower() or "non-UTF-8" in result


# --- read_files batch function ---


def test_read_files_batch(tmp_path):
    file_a = tmp_path / "a.txt"
    file_b = tmp_path / "b.txt"
    file_a.write_text("content a")
    file_b.write_text("content b")

    results = read_files([str(file_a), str(file_b)])
    assert isinstance(results, dict)
    assert "content a" in results[str(file_a)]
    assert "content b" in results[str(file_b)]


def test_read_files_batch_with_missing_file(tmp_path):
    file_a = tmp_path / "a.txt"
    file_a.write_text("content a")
    missing = str(tmp_path / "missing.txt")

    results = read_files([str(file_a), missing])
    assert "content a" in results[str(file_a)]
    assert "Error" in results[missing]


# --- write_file exception path ---


def test_write_file_invalid_path(tmp_path):
    # Create a file, then try to write into it as if it's a directory
    existing_file = tmp_path / "existing.txt"
    existing_file.write_text("exists")
    invalid_path = str(existing_file) + "/subfile.txt"

    result = write_file(invalid_path, "content")
    assert "Error" in result


# --- write_files batch function ---


def test_write_files_batch_success(tmp_path):
    file_a = str(tmp_path / "a.txt")
    file_b = str(tmp_path / "b.txt")

    results = write_files(
        [
            {"path": file_a, "content": "hello a"},
            {"path": file_b, "content": "hello b"},
        ]
    )

    assert "Successfully wrote" in results[file_a]
    assert "Successfully wrote" in results[file_b]
    assert (tmp_path / "a.txt").read_text() == "hello a"
    assert (tmp_path / "b.txt").read_text() == "hello b"


def test_write_files_batch_missing_path_or_content(tmp_path):
    file_a = str(tmp_path / "a.txt")

    results = write_files(
        [
            {"path": file_a, "content": "hello"},
            {"path": None, "content": "orphan"},
            {"path": str(tmp_path / "no_content.txt")},
        ]
    )

    assert "Successfully wrote" in results[file_a]
    assert "Error: Missing path or content" in results["None"]
    assert "Error: Missing path or content" in results[str(tmp_path / "no_content.txt")]


# --- replace_in_file additional coverage ---


def test_replace_in_file_nonexistent_file(tmp_path):
    result = replace_in_file(str(tmp_path / "ghost.txt"), "old", "new")
    assert "Error" in result
    assert "not found" in result.lower()


def test_replace_in_file_text_not_found(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("hello world")

    result = replace_in_file(str(file_path), "nonexistent text", "replacement")
    assert "Error" in result
    assert "not found" in result.lower()


def test_replace_in_file_no_changes(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("hello world")

    result = replace_in_file(str(file_path), "hello", "hello")
    assert "No changes made" in result


def test_replace_in_file_near_match(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("hello world\ngoodbye world\n")

    # old_text first line ("hello worl") is a substring of file line but full old_text doesn't match
    result = replace_in_file(str(file_path), "hello worl\ngoodbye", "hello zrb")
    assert "not found" in result.lower()
    assert "Similar lines found" in result


def test_replace_in_file_fuzzy_trailing_whitespace(tmp_path):
    """Fuzzy match should succeed when file lines have trailing whitespace."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("hello world   \ngoodbye world   \n")

    # old_text has no trailing whitespace, file has trailing spaces
    result = replace_in_file(str(file_path), "hello world\ngoodbye world", "hi there")
    assert "Successfully updated" in result
    assert "fuzzy match" in result.lower()
    assert "hi there" in file_path.read_text()


def test_replace_in_file_fuzzy_indentation_flexible(tmp_path):
    """Fuzzy match should succeed when indentation differs by a common prefix."""
    file_path = tmp_path / "test.py"
    file_path.write_text("    def foo():\n        pass\n")

    # old_text uses a different but consistent indentation level
    result = replace_in_file(
        str(file_path), "def foo():\n    pass", "def bar():\n    return 1"
    )
    assert "Successfully updated" in result
    assert "fuzzy match" in result.lower()
    content = file_path.read_text()
    assert "bar" in content


def test_replace_in_file_multiple_matches(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("foo bar foo baz")

    # Without count, replaces all
    result = replace_in_file(str(file_path), "foo", "FOO")
    assert "Successfully updated" in result
    with open(file_path) as f:
        assert f.read() == "FOO bar FOO baz"

    # With count=1, replaces first only
    file_path.write_text("foo bar foo baz")
    result = replace_in_file(str(file_path), "foo", "FOO", count=1)
    assert "Successfully updated" in result
    with open(file_path) as f:
        assert f.read() == "FOO bar foo baz"


# --- search_files additional coverage ---


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
    assert len(result["results"]) == 500  # 250 head + 250 tail


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
