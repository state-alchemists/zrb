"""Tests for RAG tool implementation."""

import pytest

from zrb.llm.tool.rag import RAGFileReader, create_rag_from_directory


class TestRAGFileReader:
    """Test public RAGFileReader functionality."""

    def test_rag_file_reader_match(self):
        reader = RAGFileReader("*.txt", lambda x: "content")
        assert reader.is_match("test.txt")
        assert reader.is_match("path/to/test.txt")
        assert not reader.is_match("test.pdf")

    def test_rag_file_reader_match_with_path(self):
        reader = RAGFileReader("docs/*.md", lambda x: "content")
        assert reader.is_match("docs/readme.md")

    def test_rag_file_reader_handles_alternative_separator(self):
        reader = RAGFileReader("*.py", lambda x: "content")
        assert reader.is_match("/src/module.py") is True


class TestRAGFactory:
    """Test RAG tool creation via factory."""

    def test_create_rag_from_directory_is_functional(self):
        import inspect

        # We test that the factory produces a valid async function (the tool)
        # We avoid testing the private hash/load helpers as per mandate
        retrieve = create_rag_from_directory(
            tool_name="test_tool", tool_description="test description"
        )

        assert inspect.iscoroutinefunction(retrieve)
        assert retrieve.__name__ == "test_tool"
        assert "test description" in retrieve.__doc__
        assert "MANDATES" in retrieve.__doc__
