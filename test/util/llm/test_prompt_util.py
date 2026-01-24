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
