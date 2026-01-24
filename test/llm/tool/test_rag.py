import os

import pytest

from zrb.llm.tool.rag import (
    RAGFileReader,
    _compute_file_hash,
    _load_hashes,
    _save_hashes,
)


def test_rag_file_reader_match():
    reader = RAGFileReader("*.txt", lambda x: "content")
    assert reader.is_match("test.txt")
    assert reader.is_match("path/to/test.txt")
    assert not reader.is_match("test.pdf")


def test_rag_file_reader_match_with_path():
    reader = RAGFileReader("docs/*.md", lambda x: "content")
    assert reader.is_match("docs/readme.md")
    # fnmatch matches full path if separator is present
    # depending on OS it might behave differently but docs/*.md usually matches docs/something.md


def test_compute_file_hash(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello")
    h1 = _compute_file_hash(str(f))
    f.write_text("hello world")
    h2 = _compute_file_hash(str(f))
    assert h1 != h2


def test_save_load_hashes(tmp_path):
    f = tmp_path / "hashes.json"
    hashes = {"file1": "hash1", "file2": "hash2"}
    _save_hashes(str(f), hashes)
    loaded = _load_hashes(str(f))
    assert loaded == hashes


def test_load_hashes_non_existent():
    assert _load_hashes("/non/existent/path") == {}


def test_create_rag_from_directory_factory():
    from zrb.llm.tool.rag import create_rag_from_directory

    retrieve = create_rag_from_directory(
        tool_name="test_tool", tool_description="test description"
    )
    assert callable(retrieve)
    assert retrieve.__name__ == "test_tool"
    assert "test description" in retrieve.__doc__
