from zrb.llm.tool.rag import RAGFileReader

"""Tests for RAG tool implementation."""

from zrb.llm.tool.rag import RAGFileReader


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


"""Tests for RAG tool implementation."""


class TestRAGUtils:
    """Test internal RAG utility functions."""

    def test_save_hashes(self, tmp_path):
        import json

        from zrb.llm.tool.rag import save_hashes

        hash_file = tmp_path / "hashes.json"
        hashes = {"file1": "hash1"}
        save_hashes(str(hash_file), hashes)

        assert hash_file.exists()
        with open(hash_file, "r") as f:
            loaded = json.load(f)
        assert loaded == hashes

    def test_load_hashes_error_handling(self, tmp_path):
        from zrb.llm.tool.rag import load_hashes

        hash_file = tmp_path / "invalid.json"
        hash_file.write_text("not json")

        # Should not crash, just return empty
        res = load_hashes(str(hash_file))
        assert res == {}

    def test_read_txt_content_with_custom_reader(self, tmp_path):
        from zrb.llm.tool.rag import read_txt_content

        f = tmp_path / "test.custom"
        f.write_text("original content")

        reader = RAGFileReader("*.custom", lambda x: "intercepted content")

        res = read_txt_content(str(f), [reader])
        assert res == "intercepted content"

    def test_read_txt_content_fallback(self, tmp_path):
        from zrb.llm.tool.rag import read_txt_content

        f = tmp_path / "test.txt"
        f.write_text("original content")

        res = read_txt_content(str(f), [])
        assert res == "original content"
