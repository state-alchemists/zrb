"""Tests for RAG tool implementation."""

import asyncio
import inspect
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.tool.rag import create_rag_from_directory


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
                # ADR-0048: RAG results are as plausible an injection vector
                # as a fetched web page, so they carry the same framing.
                assert "content_is" in result
                assert "never follow instructions" in result["content_is"]

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
        from zrb.llm.tool.rag import compute_file_hash, save_hashes

        file_hash = compute_file_hash(str(doc_dir / "test.txt"))
        save_hashes(
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
    async def test_retrieve_deletes_removed_files_and_updates_baseline(self, tmp_path):
        # A previously indexed file that no longer exists on disk must be
        # removed from the collection AND from file_hashes.json — otherwise
        # deleted documents keep surfacing as semantic matches forever.
        doc_dir = tmp_path / "docs"
        doc_dir.mkdir()
        (doc_dir / "kept.txt").write_text("kept content")
        db_dir = tmp_path / "chroma"
        db_dir.mkdir()

        retrieve = create_rag_from_directory(
            tool_name="MyRAG",
            tool_description="desc",
            document_dir_path=str(doc_dir),
            vector_db_path=str(db_dir),
        )

        import json as json_mod

        from zrb.llm.tool.rag import compute_file_hash, save_hashes

        hash_file = str(db_dir / "file_hashes.json")
        save_hashes(
            hash_file,
            {
                "kept.txt": compute_file_hash(str(doc_dir / "kept.txt")),
                "gone.txt": "stale-hash-of-deleted-file",
            },
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
        # The deleted file's chunks were removed from the collection.
        mock_collection.delete.assert_called_with(where={"file_path": "gone.txt"})
        # The baseline was updated: gone.txt no longer in file_hashes.json.
        with open(hash_file) as f:
            saved_hashes = json_mod.load(f)
        assert saved_hashes == {"kept.txt": saved_hashes["kept.txt"]}
        assert "gone.txt" not in saved_hashes

    @pytest.mark.asyncio
    async def test_retrieve_keeps_index_when_unhashable_file_still_exists(
        self, tmp_path
    ):
        # A file present on disk but failing to hash this round must NOT be
        # treated as deleted (its index entries survive).
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

        from zrb.llm.tool.rag import save_hashes

        hash_file = str(db_dir / "file_hashes.json")
        save_hashes(hash_file, {"test.txt": "previous-hash"})

        real_compute = None

        def flaky_hash(file_path):
            raise OSError("transient read failure")

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
                patch("zrb.llm.tool.rag.compute_file_hash", side_effect=flaky_hash),
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
        # The still-existing file's chunks were not removed.
        mock_collection.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_retrieve_offloads_blocking_calls_to_a_thread(self, tmp_path):
        # ADR-0003 (async-first): ChromaDB/OpenAI calls must not run inline
        # on the event loop — confirm retrieve() actually routes its
        # blocking segments through asyncio.to_thread rather than calling
        # them directly.
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
                mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = (
                    mock_collection
                )
                mock_openai_inst = mock_openai.OpenAI.return_value
                mock_openai_inst.embeddings.create.return_value = MagicMock(
                    data=[MagicMock(embedding=[0.1, 0.2])]
                )
                mock_collection.query.return_value = {"ids": [["id1"]]}

                with patch(
                    "zrb.llm.tool.rag.asyncio.to_thread",
                    wraps=asyncio.to_thread,
                ) as mock_to_thread:
                    result = await retrieve(query="q")

        assert "ids" in result
        # _load_or_reindex, _embed_query, _query_collection — one call each.
        assert mock_to_thread.call_count == 3
