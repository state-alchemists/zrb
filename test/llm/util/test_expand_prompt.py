"Tests for llm/util/prompt.py - expand_prompt functionality."

import os
import tempfile

from zrb.llm.util.prompt import (
    expand_prompt,
    get_path_references,
    process_path_reference,
)


class TestExpandPrompt:
    def test_expand_prompt_empty_string(self):
        "Test that empty string returns empty string."
        assert expand_prompt("") == ""

    def test_expand_prompt_no_references(self):
        "Test that prompt without @ references returns unchanged."
        prompt = "Hello world, this is a test"
        assert expand_prompt(prompt) == prompt

    def test_expand_prompt_with_valid_file_reference(self):
        "Test expanding a valid file reference."
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test file content")
            f.flush()
            temp_path = f.name

        try:
            prompt = f"Check @{temp_path}"
            result = expand_prompt(prompt)

            assert "Appendix" in result
            assert "File Content:" in result
            assert "test file content" in result
        finally:
            os.unlink(temp_path)

    def test_expand_prompt_with_invalid_reference(self):
        "Test that invalid @ reference is left unchanged."
        prompt = "Check @/nonexistent/path/file.txt"
        result = expand_prompt(prompt)

        assert "@/nonexistent/path/file.txt" in result

    def test_expand_prompt_with_directory_reference(self):
        "Test expanding a directory reference."
        with tempfile.TemporaryDirectory() as tmpdir:

            with open(os.path.join(tmpdir, "file1.txt"), "w") as f:
                f.write("content1")
            with open(os.path.join(tmpdir, "file2.txt"), "w") as f:
                f.write("content2")

            prompt = f"Check @{tmpdir}"
            result = expand_prompt(prompt)

            assert "Appendix" in result
            assert "Directory Listing:" in result

    def test_expand_prompt_preserves_text_around_references(self):
        "Test that text around @ references is preserved."
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

    def test_a_path_with_an_at_sign_is_not_expanded(self):
        "The @ in a directory name is part of the path, not a reference marker."
        with tempfile.TemporaryDirectory() as tmpdir:
            at_dir = os.path.join(tmpdir, "@scope")
            os.makedirs(at_dir)
            with open(os.path.join(at_dir, "AGENTS.md"), "w") as f:
                f.write("RULES THAT WERE NAMED")
            os.makedirs(os.path.join(tmpdir, "scope"))
            with open(os.path.join(tmpdir, "scope", "AGENTS.md"), "w") as f:
                f.write("A FILE NOBODY NAMED")

            prompt = f"#### Instructions from: `{os.path.join(at_dir, 'AGENTS.md')}`"
            previous = os.getcwd()
            os.chdir(tmpdir)
            try:
                result = expand_prompt(prompt)
            finally:
                os.chdir(previous)

            assert "A FILE NOBODY NAMED" not in result
            assert result == prompt


class TestGetPathReferences:
    def test_get_path_references_no_references(self):
        "Test prompt without @ references returns empty list."
        matches = get_path_references("hello world")
        assert matches == []

    def test_get_path_references_empty_string(self):
        "Test empty string returns empty list."
        matches = get_path_references("")
        assert matches == []

    def test_get_path_references_single_path(self):
        "Test finding a single @ reference."
        matches = get_path_references("Check @file.txt")
        assert len(matches) == 1
        assert matches[0].group("path") == "file.txt"

    def test_get_path_references_multiple_paths(self):
        "Test finding multiple @ references."
        matches = get_path_references("Check @file1.txt and @file2.py")
        assert len(matches) == 2
        assert matches[0].group("path") == "file1.txt"
        assert matches[1].group("path") == "file2.py"

    def test_get_path_references_with_path_separators(self):
        "Test @ reference with path separators."
        matches = get_path_references("Check @src/lib/file.py")
        assert len(matches) == 1
        assert matches[0].group("path") == "src/lib/file.py"

    def test_get_path_references_with_home_dir(self):
        "Test @ reference with home directory."
        matches = get_path_references("Check @~/file.txt")
        assert len(matches) == 1
        assert matches[0].group("path") == "~/file.txt"

    def test_an_at_inside_a_path_is_not_a_reference(self):
        "`/work/@scope/AGENTS.md` is one path; its @ is not a marker."
        assert get_path_references("/work/@scope/AGENTS.md") == []
        assert get_path_references("`C:\\work\\@scope\\AGENTS.md`") == []

    def test_an_at_inside_a_word_is_not_a_reference(self):
        "An address is not a prompt reference either."
        assert get_path_references("mail go@example.com") == []

    def test_an_at_after_a_dot_or_a_dash_is_not_a_reference(self):
        "`pkg.@beta` and `pkg-@beta` are directory names, not markers."
        assert get_path_references("/work/pkg.@beta/AGENTS.md") == []
        assert get_path_references("/work/pkg-@beta/AGENTS.md") == []


class TestProcessPathReference:
    def test_process_path_reference_valid_file(self):
        "Test processing a valid file path."
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test content")
            f.flush()
            temp_path = f.name

        try:
            header, content, is_valid = process_path_reference(temp_path)
            assert is_valid is True
            assert "File Content:" in header
            assert content == "test content"
        finally:
            os.unlink(temp_path)

    def test_process_path_reference_valid_directory(self):
        "Test processing a valid directory path."
        with tempfile.TemporaryDirectory() as tmpdir:

            with open(os.path.join(tmpdir, "test.txt"), "w") as f:
                f.write("test")

            header, content, is_valid = process_path_reference(tmpdir)
            assert is_valid is True
            assert "Directory Listing:" in header
            assert "test.txt" in content

    def test_process_path_reference_nonexistent_path(self):
        "Test processing a nonexistent path."
        header, content, is_valid = process_path_reference("/nonexistent/path/file.txt")
        assert is_valid is False
        assert header == ""
        assert content == ""

    def test_process_path_reference_empty_directory(self):
        "Test processing an empty directory."
        with tempfile.TemporaryDirectory() as tmpdir:
            header, content, is_valid = process_path_reference(tmpdir)
            assert is_valid is True
            assert "Directory Listing:" in header
            assert content == "(Empty directory)"
