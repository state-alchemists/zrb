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


def test_expand_prompt_file_specific_warning(tmp_path):
    """Test that file references generate specific read_file warning."""
    f = tmp_path / "test.txt"
    f.write_text("file content")
    prompt = f"read @{f}"
    expanded = expand_prompt(prompt)

    # Should have specific read_file warning (full phrase with formatting)
    assert "> **DO NOT** use `read_file` to read this path again." in expanded
    # Should NOT have list_files warning for files
    assert "> **DO NOT** use `list_files` to read this path again." not in expanded
    # Should contain file content
    assert "file content" in expanded


def test_expand_prompt_directory_specific_warning(tmp_path):
    """Test that directory references generate specific list_files warning."""
    # Create a directory with a file
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    f = subdir / "test.txt"
    f.write_text("file content")

    prompt = f"list @{tmp_path}"
    expanded = expand_prompt(prompt)

    # Should have specific list_files warning (full phrase with formatting)
    assert "> **DO NOT** use `list_files` to read this path again." in expanded
    # Should NOT have read_file warning for directories
    assert "> **DO NOT** use `read_file` to read this path again." not in expanded
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

    # Should have both warnings in their respective sections (full phrases with formatting)
    assert "> **DO NOT** use `read_file` to read this path again." in expanded
    assert "> **DO NOT** use `list_files` to read this path again." in expanded
    # Should contain both contents
    assert "file content" in expanded
    assert "docs" in expanded
