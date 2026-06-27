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
        assert "natural-language query" in retrieve.__doc__

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
    async def test_retrieve_overlap_ge_chunk_size_does_not_hang(self, tmp_path):
        # B13 (rag.py:153): overlap >= chunk_size must not cause a zero/negative
        # range step (infinite loop / ValueError) during chunking.
        doc_dir = tmp_path / "docs"
        doc_dir.mkdir()
        (doc_dir / "test.txt").write_text("some knowledge content for chunking")

        db_dir = tmp_path / "chroma"
        db_dir.mkdir()

        retrieve = create_rag_from_directory(
            tool_name="MyRAG",
            tool_description="desc",
            document_dir_path=str(doc_dir),
            vector_db_path=str(db_dir),
            chunk_size=10,
            overlap=20,  # overlap > chunk_size
        )

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
                mock_collection.query.return_value = {"ids": [["id1"]]}

                result = await retrieve(query="test query")
                assert "ids" in result

    @pytest.mark.asyncio
    async def test_create_rag_default_file_reader_not_shared(self):
        # B13 (rag.py:42): mutable default must be replaced with None sentinel;
        # the factory must still work when file_reader is omitted.
        retrieve = create_rag_from_directory(tool_name="MyRAG", tool_description="desc")
        assert inspect.iscoroutinefunction(retrieve)

    @pytest.mark.asyncio
    async def test_retrieve_missing_dependency(self):
        # rag.py:71-72: ImportError fallback when chromadb/openai missing.
        retrieve = create_rag_from_directory(tool_name="MyRAG", tool_description="desc")

        import builtins

        real_import = builtins.__import__

        def _raise_for_chromadb(name, *args, **kwargs):
            if name.startswith("chromadb") or name == "openai":
                raise ImportError("No module named chromadb")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_raise_for_chromadb):
            result = await retrieve(query="test query")
        assert "error" in result
        assert "Missing required dependency" in result["error"]
        assert "pip install chromadb openai" in result["error"]

    @pytest.mark.asyncio
    async def test_retrieve_with_base_url_and_explicit_params(self, tmp_path):
        # rag.py:94: base_url branch builds OpenAI(api_key, base_url). Also
        # exercises explicit api_key/base_url/embedding_model args overriding CFG.
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
                mock_collection = MagicMock()
                mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
                    mock_collection
                )
                mock_openai_inst = mock_openai.OpenAI.return_value
                mock_openai_inst.embeddings.create.return_value = MagicMock(
                    data=[MagicMock(embedding=[0.1, 0.2])]
                )
                mock_collection.query.return_value = {"ids": [["id1"]]}

                result = await retrieve(
                    query="q",
                    api_key="explicit-key",
                    base_url="http://localhost:11434",
                    embedding_model="my-model",
                )

        assert "ids" in result
        mock_openai.OpenAI.assert_called_once_with(
            api_key="explicit-key", base_url="http://localhost:11434"
        )

    @pytest.mark.asyncio
    async def test_retrieve_openai_init_failure(self, tmp_path):
        # rag.py:97-98: exception while initializing the embedding client.
        retrieve = create_rag_from_directory(tool_name="MyRAG", tool_description="desc")
        mock_chroma = MagicMock()
        mock_chroma_config = MagicMock()
        mock_openai = MagicMock()
        mock_openai.OpenAI.side_effect = RuntimeError("bad url")
        with patch.dict(
            "sys.modules",
            {
                "chromadb": mock_chroma,
                "chromadb.config": mock_chroma_config,
                "openai": mock_openai,
            },
        ):
            with patch("zrb.llm.tool.rag.CFG") as mock_cfg:
                mock_cfg.RAG_EMBEDDING_API_KEY = "dummy"
                mock_cfg.RAG_EMBEDDING_BASE_URL = None
                mock_cfg.RAG_EMBEDDING_MODEL = "model"
                result = await retrieve(query="q")
        assert "error" in result
        assert "Failed to initialize embedding client" in result["error"]

    @pytest.mark.asyncio
    async def test_retrieve_chromadb_init_failure(self, tmp_path):
        # rag.py:107-108: exception while initializing ChromaDB.
        retrieve = create_rag_from_directory(tool_name="MyRAG", tool_description="desc")
        mock_chroma = MagicMock()
        mock_chroma.PersistentClient.side_effect = RuntimeError("locked")
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
                mock_cfg.RAG_EMBEDDING_API_KEY = "dummy"
                mock_cfg.RAG_EMBEDDING_BASE_URL = None
                mock_cfg.RAG_EMBEDDING_MODEL = "model"
                result = await retrieve(query="q")
        assert "error" in result
        assert "Failed to initialize ChromaDB" in result["error"]

    @pytest.mark.asyncio
    async def test_retrieve_document_dir_not_found(self, tmp_path):
        # rag.py:123: missing document directory yields a clear error.
        retrieve = create_rag_from_directory(
            tool_name="MyRAG",
            tool_description="desc",
            document_dir_path=str(tmp_path / "does-not-exist"),
            vector_db_path=str(tmp_path / "chroma"),
        )
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
                mock_cfg.RAG_EMBEDDING_API_KEY = "dummy"
                mock_cfg.RAG_EMBEDDING_BASE_URL = None
                mock_cfg.RAG_EMBEDDING_MODEL = "model"
                result = await retrieve(query="q")
        assert "error" in result
        assert "Document directory not found" in result["error"]

    @pytest.mark.asyncio
    async def test_retrieve_no_changes_skips_update(self, tmp_path):
        # rag.py:185: when hashes match, indexing is skipped (no embeddings for
        # documents, only the query embedding is produced).
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

        # Pre-seed the hash file so the single document is unchanged.
        from zrb.llm.tool.rag import _compute_file_hash, _save_hashes

        file_hash = _compute_file_hash(str(doc_dir / "test.txt"))
        _save_hashes(
            str(db_dir / "file_hashes.json"),
            {"test.txt": file_hash},
        )

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
                mock_cfg.RAG_EMBEDDING_MODEL = "model"
                mock_cfg.RAG_EMBEDDING_BASE_URL = None
                mock_collection = MagicMock()
                mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
                    mock_collection
                )
                mock_openai_inst = mock_openai.OpenAI.return_value
                mock_openai_inst.embeddings.create.return_value = MagicMock(
                    data=[MagicMock(embedding=[0.1, 0.2])]
                )
                mock_collection.query.return_value = {"ids": [["id1"]]}

                result = await retrieve(query="q")

        assert "ids" in result
        mock_collection.upsert.assert_not_called()
        # Only the query is embedded (no per-chunk embedding work).
        assert mock_openai_inst.embeddings.create.call_count == 1

    @pytest.mark.asyncio
    async def test_retrieve_processing_file_error_is_caught(self, tmp_path):
        # rag.py:179-180: an exception while processing a changed file is logged
        # and swallowed; the query still proceeds.
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
                mock_cfg.RAG_EMBEDDING_MODEL = "model"
                mock_cfg.RAG_EMBEDDING_BASE_URL = None
                mock_collection = MagicMock()
                # collection.delete raises only during indexing, not query.
                mock_collection.delete.side_effect = RuntimeError("delete failed")
                mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
                    mock_collection
                )
                mock_openai_inst = mock_openai.OpenAI.return_value
                mock_openai_inst.embeddings.create.return_value = MagicMock(
                    data=[MagicMock(embedding=[0.1, 0.2])]
                )
                mock_collection.query.return_value = {"ids": [["id1"]]}

                result = await retrieve(query="q")

        # Processing failed and was swallowed; the query still ran successfully.
        assert "ids" in result

    @pytest.mark.asyncio
    async def test_retrieve_query_embedding_auth_error(self, tmp_path):
        # rag.py:197-202: 401/Unauthorized on the query embedding.
        result = await self._run_with_query_embedding_error(
            tmp_path, RuntimeError("401 Unauthorized")
        )
        assert "error" in result
        assert "authentication failed" in result["error"]

    @pytest.mark.asyncio
    async def test_retrieve_query_embedding_rate_limit_error(self, tmp_path):
        # rag.py:203-206: 429/rate limit on the query embedding.
        result = await self._run_with_query_embedding_error(
            tmp_path, RuntimeError("429 rate limit reached")
        )
        assert "error" in result
        assert "rate limit exceeded" in result["error"]

    @pytest.mark.asyncio
    async def test_retrieve_query_embedding_generic_error(self, tmp_path):
        # rag.py:207-210: any other failure generating the query embedding.
        result = await self._run_with_query_embedding_error(
            tmp_path, RuntimeError("model not found")
        )
        assert "error" in result
        assert "Failed to generate query embedding" in result["error"]

    async def _run_with_query_embedding_error(self, tmp_path, exc):
        """Helper: run retrieve where ONLY the query embedding raises ``exc``.

        Indexing is skipped (pre-seeded hashes) so the only embeddings.create
        call is for the query itself.
        """
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

        from zrb.llm.tool.rag import _compute_file_hash, _save_hashes

        _save_hashes(
            str(db_dir / "file_hashes.json"),
            {"test.txt": _compute_file_hash(str(doc_dir / "test.txt"))},
        )

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
                mock_cfg.RAG_EMBEDDING_MODEL = "model"
                mock_cfg.RAG_EMBEDDING_BASE_URL = None
                mock_collection = MagicMock()
                mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
                    mock_collection
                )
                mock_openai_inst = mock_openai.OpenAI.return_value
                mock_openai_inst.embeddings.create.side_effect = exc
                return await retrieve(query="q")

    @pytest.mark.asyncio
    async def test_retrieve_load_hashes_failure_is_caught(self, tmp_path):
        # rag.py:115-117: if loading previous hashes raises, it is logged and we
        # fall back to an empty hash map (treating everything as changed).
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
            with (
                patch("zrb.llm.tool.rag.CFG") as mock_cfg,
                patch(
                    "zrb.llm.tool.rag._load_hashes", side_effect=RuntimeError("boom")
                ),
            ):
                mock_cfg.RAG_CHUNK_SIZE = 100
                mock_cfg.RAG_OVERLAP = 0
                mock_cfg.RAG_MAX_RESULT_COUNT = 5
                mock_cfg.RAG_EMBEDDING_API_KEY = "dummy"
                mock_cfg.RAG_EMBEDDING_MODEL = "model"
                mock_cfg.RAG_EMBEDDING_BASE_URL = None
                mock_collection = MagicMock()
                mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
                    mock_collection
                )
                mock_openai_inst = mock_openai.OpenAI.return_value
                mock_openai_inst.embeddings.create.return_value = MagicMock(
                    data=[MagicMock(embedding=[0.1, 0.2])]
                )
                mock_collection.query.return_value = {"ids": [["id1"]]}

                result = await retrieve(query="q")

        assert "ids" in result

    @pytest.mark.asyncio
    async def test_retrieve_hashing_file_error_is_caught(self, tmp_path):
        # rag.py:136-137: an error computing a file's hash is logged and skipped;
        # the query still proceeds.
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
            with (
                patch("zrb.llm.tool.rag.CFG") as mock_cfg,
                patch(
                    "zrb.llm.tool.rag._compute_file_hash",
                    side_effect=OSError("unreadable"),
                ),
            ):
                mock_cfg.RAG_CHUNK_SIZE = 100
                mock_cfg.RAG_OVERLAP = 0
                mock_cfg.RAG_MAX_RESULT_COUNT = 5
                mock_cfg.RAG_EMBEDDING_API_KEY = "dummy"
                mock_cfg.RAG_EMBEDDING_MODEL = "model"
                mock_cfg.RAG_EMBEDDING_BASE_URL = None
                mock_collection = MagicMock()
                mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
                    mock_collection
                )
                mock_openai_inst = mock_openai.OpenAI.return_value
                mock_openai_inst.embeddings.create.return_value = MagicMock(
                    data=[MagicMock(embedding=[0.1, 0.2])]
                )
                mock_collection.query.return_value = {"ids": [["id1"]]}

                result = await retrieve(query="q")

        # Hashing failed for the only file → nothing indexed, but query succeeds.
        assert "ids" in result
        mock_collection.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_retrieve_collection_query_failure(self, tmp_path):
        # rag.py:220-221: collection.query raising returns a reset suggestion.
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

        from zrb.llm.tool.rag import _compute_file_hash, _save_hashes

        _save_hashes(
            str(db_dir / "file_hashes.json"),
            {"test.txt": _compute_file_hash(str(doc_dir / "test.txt"))},
        )

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
                mock_cfg.RAG_EMBEDDING_MODEL = "model"
                mock_cfg.RAG_EMBEDDING_BASE_URL = None
                mock_collection = MagicMock()
                mock_collection.query.side_effect = RuntimeError("corrupt index")
                mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
                    mock_collection
                )
                mock_openai_inst = mock_openai.OpenAI.return_value
                mock_openai_inst.embeddings.create.return_value = MagicMock(
                    data=[MagicMock(embedding=[0.1, 0.2])]
                )
                result = await retrieve(query="q")

        assert "error" in result
        assert "Failed to search documents" in result["error"]

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
