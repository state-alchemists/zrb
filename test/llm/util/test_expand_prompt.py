"""Tests for llm/util/prompt.py - expand_prompt functionality."""

import os
import tempfile

import pytest

from zrb.llm.util.prompt import (
    _get_path_references,
    _process_path_reference,
    expand_prompt,
)


class TestExpandPrompt:
    def test_expand_prompt_empty_string(self):
        """Test that empty string returns empty string."""
        assert expand_prompt("") == ""

    def test_expand_prompt_no_references(self):
        """Test that prompt without @ references returns unchanged."""
        prompt = "Hello world, this is a test"
        assert expand_prompt(prompt) == prompt

    def test_expand_prompt_with_valid_file_reference(self):
        """Test expanding a valid file reference."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test file content")
            f.flush()
            temp_path = f.name

        try:
            prompt = f"Check @{temp_path}"
            result = expand_prompt(prompt)
            # Should have appendix with file content
            assert "Appendix" in result
            assert "File Content:" in result
            assert "test file content" in result
        finally:
            os.unlink(temp_path)

    def test_expand_prompt_with_invalid_reference(self):
        """Test that invalid @ reference is left unchanged."""
        prompt = "Check @/nonexistent/path/file.txt"
        result = expand_prompt(prompt)
        # Should preserve the original token for invalid references
        assert "@/nonexistent/path/file.txt" in result

    def test_expand_prompt_with_directory_reference(self):
        """Test expanding a directory reference."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some files in the directory
            with open(os.path.join(tmpdir, "file1.txt"), "w") as f:
                f.write("content1")
            with open(os.path.join(tmpdir, "file2.txt"), "w") as f:
                f.write("content2")

            prompt = f"Check @{tmpdir}"
            result = expand_prompt(prompt)
            # Should have appendix with directory listing
            assert "Appendix" in result
            assert "Directory Listing:" in result

    def test_expand_prompt_preserves_text_around_references(self):
        """Test that text around @ references is preserved."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("content")
            f.flush()
            temp_path = f.name

        try:
            prompt = f"Before @{temp_path} after"
            result = expand_prompt(prompt)
            assert "Before" in result
            assert "after" in result
        finally:
            os.unlink(temp_path)


class TestGetPathReferences:
    def test_get_path_references_no_references(self):
        """Test prompt without @ references returns empty list."""
        matches = _get_path_references("hello world")
        assert matches == []

    def test_get_path_references_empty_string(self):
        """Test empty string returns empty list."""
        matches = _get_path_references("")
        assert matches == []

    def test_get_path_references_single_path(self):
        """Test finding a single @ reference."""
        matches = _get_path_references("Check @file.txt")
        assert len(matches) == 1
        assert matches[0].group("path") == "file.txt"

    def test_get_path_references_multiple_paths(self):
        """Test finding multiple @ references."""
        matches = _get_path_references("Check @file1.txt and @file2.py")
        assert len(matches) == 2
        assert matches[0].group("path") == "file1.txt"
        assert matches[1].group("path") == "file2.py"

    def test_get_path_references_with_path_separators(self):
        """Test @ reference with path separators."""
        matches = _get_path_references("Check @src/lib/file.py")
        assert len(matches) == 1
        assert matches[0].group("path") == "src/lib/file.py"

    def test_get_path_references_with_home_dir(self):
        """Test @ reference with home directory."""
        matches = _get_path_references("Check @~/file.txt")
        assert len(matches) == 1
        assert matches[0].group("path") == "~/file.txt"


class TestProcessPathReference:
    def test_process_path_reference_valid_file(self):
        """Test processing a valid file path."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test content")
            f.flush()
            temp_path = f.name

        try:
            header, content, is_valid = _process_path_reference(temp_path)
            assert is_valid is True
            assert "File Content:" in header
            assert content == "test content"
        finally:
            os.unlink(temp_path)

    def test_process_path_reference_valid_directory(self):
        """Test processing a valid directory path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file in the directory
            with open(os.path.join(tmpdir, "test.txt"), "w") as f:
                f.write("test")

            header, content, is_valid = _process_path_reference(tmpdir)
            assert is_valid is True
            assert "Directory Listing:" in header
            assert "test.txt" in content

    def test_process_path_reference_nonexistent_path(self):
        """Test processing a nonexistent path."""
        header, content, is_valid = _process_path_reference(
            "/nonexistent/path/file.txt"
        )
        assert is_valid is False
        assert header == ""
        assert content == ""

    def test_process_path_reference_empty_directory(self):
        """Test processing an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            header, content, is_valid = _process_path_reference(tmpdir)
            assert is_valid is True
            assert "Directory Listing:" in header
            assert content == "(Empty directory)"
