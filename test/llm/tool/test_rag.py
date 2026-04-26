"""Tests for RAG tool implementation."""

import inspect
from unittest.mock import MagicMock, patch

import pytest
import ulid

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
        # We test that the factory produces a valid async function (the tool)
        retrieve = create_rag_from_directory(
            tool_name="test_tool", tool_description="test description"
        )

        assert inspect.iscoroutinefunction(retrieve)
        assert retrieve.__name__ == "test_tool"
        assert "test description" in retrieve.__doc__
        assert "MANDATES" in retrieve.__doc__

    @pytest.mark.asyncio
    async def test_retrieve_logic(self, tmp_path):
        doc_dir = tmp_path / "docs"
        doc_dir.mkdir()
        (doc_dir / "test.txt").write_text("knowledge content")

        db_dir = tmp_path / "chroma"
        db_dir.mkdir()

        retrieve = create_rag_from_directory(
            tool_name="MyRAG",
            tool_description="desc",
            document_dir_path=str(doc_dir),
            vector_db_path=str(db_dir),
        )

        # Mock dependencies in sys.modules
        mock_chroma = MagicMock()
        mock_chroma_config = MagicMock()
        mock_openai = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "chromadb": mock_chroma,
                "chromadb.config": mock_chroma_config,
                "openai": mock_openai,
            },
        ):
            with patch("zrb.llm.tool.rag.CFG") as mock_cfg:
                mock_cfg.RAG_CHUNK_SIZE = 100
                mock_cfg.RAG_OVERLAP = 0
                mock_cfg.RAG_MAX_RESULT_COUNT = 5
                mock_cfg.RAG_EMBEDDING_API_KEY = "dummy"
                mock_cfg.RAG_EMBEDDING_MODEL = "text-embedding-3-small"
                mock_cfg.RAG_EMBEDDING_BASE_URL = None

                mock_collection = MagicMock()
                mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
                    mock_collection
                )

                mock_openai_inst = mock_openai.OpenAI.return_value
                mock_openai_inst.embeddings.create.return_value = MagicMock(
                    data=[MagicMock(embedding=[0.1, 0.2])]
                )

                mock_collection.query.return_value = {
                    "ids": [["id1"]],
                    "documents": [["result"]],
                }

                result = await retrieve(query="test query")

                assert "ids" in result
                assert result["ids"] == [["id1"]]
                assert mock_openai_inst.embeddings.create.called
                assert mock_collection.query.called

    @pytest.mark.asyncio
    async def test_retrieve_error_missing_key(self, tmp_path):
        retrieve = create_rag_from_directory(tool_name="MyRAG", tool_description="desc")

        # We still need to mock modules even if they are not used yet,
        # but in this case they ARE used if the check passes.
        # Actually retrieve does 'from chromadb import ...' at the start.
        mock_chroma = MagicMock()
        mock_chroma_config = MagicMock()
        mock_openai = MagicMock()
        with patch.dict(
            "sys.modules",
            {
                "chromadb": mock_chroma,
                "chromadb.config": mock_chroma_config,
                "openai": mock_openai,
            },
        ):
            with patch("zrb.llm.tool.rag.CFG") as mock_cfg:
                mock_cfg.RAG_EMBEDDING_API_KEY = None
                result = await retrieve(query="test query")
                assert "error" in result
                assert "API key" in result["error"]


class TestRAGUtils:
    """Test internal RAG utility functions."""

    def test_save_hashes(self, tmp_path):
        import json

        from zrb.llm.tool.rag import _save_hashes

        hash_file = tmp_path / "hashes.json"
        hashes = {"file1": "hash1"}
        _save_hashes(str(hash_file), hashes)

        assert hash_file.exists()
        with open(hash_file, "r") as f:
            loaded = json.load(f)
        assert loaded == hashes

    def test_load_hashes_error_handling(self, tmp_path):
        from zrb.llm.tool.rag import _load_hashes

        hash_file = tmp_path / "invalid.json"
        hash_file.write_text("not json")

        # Should not crash, just return empty
        res = _load_hashes(str(hash_file))
        assert res == {}

    def test_read_txt_content_with_custom_reader(self, tmp_path):
        from zrb.llm.tool.rag import _read_txt_content

        f = tmp_path / "test.custom"
        f.write_text("original content")

        reader = RAGFileReader("*.custom", lambda x: "intercepted content")

        res = _read_txt_content(str(f), [reader])
        assert res == "intercepted content"

    def test_read_txt_content_fallback(self, tmp_path):
        from zrb.llm.tool.rag import _read_txt_content

        f = tmp_path / "test.txt"
        f.write_text("original content")

        res = _read_txt_content(str(f), [])
        assert res == "original content"
