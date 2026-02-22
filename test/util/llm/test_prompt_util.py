import pytest

from zrb.llm.util.prompt import expand_prompt


def test_expand_prompt_no_expansion():
    prompt = "hello world"
    assert expand_prompt(prompt) == "hello world"


def test_expand_prompt_with_file(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("file content")
    prompt = f"read @{f}"
    expanded = expand_prompt(prompt)
    assert "file content" in expanded
    assert "read" in expanded


def test_expand_prompt_multiple_files(tmp_path):
    f1 = tmp_path / "test1.txt"
    f1.write_text("content 1")
    f2 = tmp_path / "test2.txt"
    f2.write_text("content 2")
    prompt = f"read @{f1} and @{f2}"
    expanded = expand_prompt(prompt)
    assert "content 1" in expanded
    assert "content 2" in expanded


def test_expand_prompt_file_reference(tmp_path):
    """Test that file references expand correctly."""
    f = tmp_path / "test.txt"
    f.write_text("file content")
    prompt = f"read @{f}"
    expanded = expand_prompt(prompt)

    # Should contain file content
    assert "file content" in expanded


def test_expand_prompt_directory_reference(tmp_path):
    """Test that directory references expand correctly."""
    # Create a directory with a file
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    f = subdir / "test.txt"
    f.write_text("file content")

    prompt = f"list @{tmp_path}"
    expanded = expand_prompt(prompt)

    # Should contain directory listing
    assert "subdir" in expanded or "(Empty directory)" in expanded


def test_expand_prompt_mixed_references(tmp_path):
    """Test mixed file and directory references."""
    # Create a file
    f = tmp_path / "test.txt"
    f.write_text("file content")

    # Create a subdirectory
    subdir = tmp_path / "docs"
    subdir.mkdir()
    subfile = subdir / "readme.md"
    subfile.write_text("# Documentation")

    prompt = f"check @{f} and @{subdir}"
    expanded = expand_prompt(prompt)

    # Should contain both contents
    assert "file content" in expanded
    assert "docs" in expanded
