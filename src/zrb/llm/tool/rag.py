import asyncio
import fnmatch
import hashlib
import json
import os
from collections.abc import Callable
from textwrap import dedent
from typing import Annotated, Any

import ulid
from pydantic import Field

from zrb.config.config import CFG
from zrb.context.any_context import zrb_print
from zrb.llm.tool_call.untrusted_data import UNTRUSTED_DATA_NOTE
from zrb.util.cli.style import stylize_error, stylize_muted
from zrb.util.file import read_file


class RAGFileReader:
    """Helper class to define custom file readers based on glob patterns."""

    def __init__(self, glob_pattern: str, read: Callable[[str], str]):
        self.glob_pattern = glob_pattern
        self.read = read

    def is_match(self, file_name: str):
        if os.sep not in self.glob_pattern and (
            os.altsep is None or os.altsep not in self.glob_pattern
        ):
            # Pattern like "*.txt" – match only the basename.
            return fnmatch.fnmatch(os.path.basename(file_name), self.glob_pattern)
        return fnmatch.fnmatch(file_name, self.glob_pattern)


def create_rag_from_directory(  # noqa: C901 -- registration/factory fn; mccabe sums nested handlers into this line, radon scores each separately (near-trivial on its own)
    tool_name: str,
    tool_description: str,
    document_dir_path: str = "./documents",
    vector_db_path: str = "./chroma",
    vector_db_collection: str = "documents",
    chunk_size: int | None = None,
    overlap: int | None = None,
    max_result_count: int | None = None,
    file_reader: list[RAGFileReader] | None = None,
    model_api_key: str | None = None,
    model_base_url: str | None = None,
    model_name: str | None = None,
):
    """Create a RAG tool that semantically searches a directory of documents.

    The documents are indexed into a ChromaDB vector database, re-indexed as
    files change.
    """
    readers = file_reader if file_reader is not None else []

    async def retrieve(
        query: Annotated[
            str,
            Field(
                description=(
                    "Natural-language query; returns the top semantic matches "
                    "from the indexed corpus."
                )
            ),
        ],
        api_key: Annotated[
            str,
            Field(
                description=(
                    "Embedding-provider API key for this call. Falls back to "
                    "this tool's configured key, then CFG.RAG_EMBEDDING_API_KEY."
                )
            ),
        ] = "",
        base_url: Annotated[
            str,
            Field(
                description=(
                    "Embedding-provider base URL (e.g. for Ollama/vLLM). Falls "
                    "back to this tool's configured URL, then "
                    "CFG.RAG_EMBEDDING_BASE_URL."
                )
            ),
        ] = "",
        embedding_model: Annotated[
            str,
            Field(
                description=(
                    "Embedding model name. Falls back to this tool's "
                    "configured model, then CFG.RAG_EMBEDDING_MODEL."
                )
            ),
        ] = "",
    ) -> dict[str, Any]:
        try:
            # lazy: heavy third-party
            from chromadb import PersistentClient
            from chromadb.config import Settings
            from openai import OpenAI
        except ImportError as e:
            return {
                "error": f"Missing required dependency: {e}. [SYSTEM SUGGESTION]: Ask the user to install the required packages: pip install chromadb openai"
            }

        api_key_val = api_key or model_api_key or CFG.RAG_EMBEDDING_API_KEY
        base_url_val = base_url or model_base_url or CFG.RAG_EMBEDDING_BASE_URL
        embedding_model_val = embedding_model or model_name or CFG.RAG_EMBEDDING_MODEL
        chunk_size_val = chunk_size if chunk_size is not None else CFG.RAG_CHUNK_SIZE
        overlap_val = overlap if overlap is not None else CFG.RAG_OVERLAP
        max_result_count_val = (
            max_result_count
            if max_result_count is not None
            else CFG.RAG_MAX_RESULT_COUNT
        )

        if not api_key_val:
            return {
                "error": "Embedding API key not configured. [SYSTEM SUGGESTION]: Ask the user for their embedding API provider key and pass it via the 'api_key' parameter. If using a non-OpenAI provider (e.g., Ollama, vLLM), also provide 'base_url' (e.g., 'http://localhost:11434') and 'embedding_model' name."
            }

        try:
            if base_url_val:
                openai_client = OpenAI(api_key=api_key_val, base_url=base_url_val)
            else:
                openai_client = OpenAI(api_key=api_key_val)
        except Exception as e:
            return {
                "error": f"Failed to initialize embedding client: {e}. [SYSTEM SUGGESTION]: The 'base_url' may be unreachable or the 'api_key' invalid. Ask the user to verify their embedding provider URL and credentials, then retry with correct values."
            }

        try:
            chroma_client = PersistentClient(
                path=vector_db_path, settings=Settings(allow_reset=True)
            )
            collection = chroma_client.get_or_create_collection(vector_db_collection)
        except Exception as e:
            return {
                "error": f"Failed to initialize ChromaDB: {e}. [SYSTEM SUGGESTION]: Ask the user to check if the vector_db_path ('{vector_db_path}') is accessible and writable. They may need to delete the directory to reset the database."
            }

        hash_file_path = os.path.join(vector_db_path, "file_hashes.json")

        # ChromaDB and the OpenAI client are synchronous; inline they would
        # freeze the event loop for the whole re-index/embed.
        reindex_error = await asyncio.to_thread(
            _load_or_reindex,
            document_dir_path=document_dir_path,
            hash_file_path=hash_file_path,
            collection=collection,
            openai_client=openai_client,
            embedding_model_val=embedding_model_val,
            chunk_size_val=chunk_size_val,
            overlap_val=overlap_val,
            readers=readers,
        )
        if reindex_error is not None:
            return reindex_error

        query_vector, embed_error = await asyncio.to_thread(
            _embed_query,
            openai_client=openai_client,
            query=query,
            embedding_model_val=embedding_model_val,
        )
        if embed_error is not None:
            return embed_error

        return await asyncio.to_thread(
            _query_collection,
            collection=collection,
            query_vector=query_vector,
            max_result_count_val=max_result_count_val,
            vector_db_path=vector_db_path,
        )

    retrieve.__name__ = tool_name
    retrieve.__doc__ = dedent(f"""
        {tool_description}

        Pass a natural-language query; returns the top semantic matches from the indexed corpus.
        """).strip()
    return retrieve


def _load_or_reindex(
    document_dir_path: str,
    hash_file_path: str,
    collection: Any,
    openai_client: Any,
    embedding_model_val: str,
    chunk_size_val: int,
    overlap_val: int,
    readers: list[RAGFileReader],
) -> dict[str, Any] | None:
    """Re-embed any new/changed file under `document_dir_path` into `collection`.

    Files that were previously indexed but no longer exist on disk have their
    chunks removed from `collection` and their entries dropped from the hash
    baseline.

    Returns an error dict if `document_dir_path` doesn't exist, else `None`.
    """
    if not os.path.exists(document_dir_path):
        return {
            "error": f"Document directory not found: {document_dir_path}. [SYSTEM SUGGESTION]: Ask the user to verify the document_dir_path. The directory may have been moved, deleted, or the path may be wrong."
        }
    try:
        previous_hashes = load_hashes(hash_file_path)
    except Exception as e:
        zrb_print(stylize_error(f"Error loading file hashes: {e}"), plain=True)
        previous_hashes = {}

    current_hashes, updated_files = _scan_document_hashes(
        document_dir_path, previous_hashes
    )
    removed_files = _remove_deleted_files(
        collection, document_dir_path, previous_hashes, current_hashes
    )

    if not updated_files and not removed_files:
        zrb_print(
            stylize_muted("No changes detected. Skipping database update."),
            plain=True,
        )
        return None
    if updated_files:
        zrb_print(
            stylize_muted(f"Updating {len(updated_files)} changed files"),
            plain=True,
        )
        for file_path in updated_files:
            _index_one_file(
                file_path,
                document_dir_path,
                collection,
                openai_client,
                embedding_model_val,
                chunk_size_val,
                overlap_val,
                readers,
            )
    # Deletions alone still update the baseline, or removed entries linger in
    # file_hashes.json and get "deleted" again next time.
    save_hashes(hash_file_path, current_hashes)
    return None


def _scan_document_hashes(
    document_dir_path: str, previous_hashes: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """Hash every file under the directory, and list the ones that changed."""
    current_hashes: dict[str, Any] = {}
    updated_files: list[str] = []
    for root, _, files in os.walk(document_dir_path):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                file_hash = compute_file_hash(file_path)
            except Exception as e:
                zrb_print(
                    stylize_error(f"Error hashing file {file_path}: {e}"),
                    plain=True,
                )
                continue
            relative_path = os.path.relpath(file_path, document_dir_path)
            current_hashes[relative_path] = file_hash
            if previous_hashes.get(relative_path) != file_hash:
                updated_files.append(file_path)
    return current_hashes, updated_files


def _remove_deleted_files(
    collection: Any,
    document_dir_path: str,
    previous_hashes: dict[str, Any],
    current_hashes: dict[str, Any],
) -> list[str]:
    """Drop chunks for files that were indexed before and are gone from disk.

    Guarded by existence so a transient hash failure (file present but
    unreadable this round) never drops live index data.
    """
    removed_files = [
        relative_path
        for relative_path in sorted(set(previous_hashes) - set(current_hashes))
        if not os.path.exists(os.path.join(document_dir_path, relative_path))
    ]
    for relative_path in removed_files:
        zrb_print(stylize_muted(f"Removing deleted file {relative_path}"), plain=True)
        try:
            collection.delete(where={"file_path": relative_path})
        except Exception as e:
            zrb_print(stylize_error(f"Error removing {relative_path}: {e}"), plain=True)
    return removed_files


def _index_one_file(
    file_path: str,
    document_dir_path: str,
    collection: Any,
    openai_client: Any,
    embedding_model_val: str,
    chunk_size_val: int,
    overlap_val: int,
    readers: list[RAGFileReader],
) -> None:
    """Replace one file's chunks in `collection` with freshly embedded ones."""
    try:
        relative_path = os.path.relpath(file_path, document_dir_path)
        collection.delete(where={"file_path": relative_path})
        content = read_txt_content(file_path, readers)
        file_id = ulid.new().str
        # overlap >= chunk_size would make the step zero or negative.
        step = max(1, chunk_size_val - overlap_val)
        for i in range(0, len(content), step):
            chunk = content[i : i + chunk_size_val]
            if not chunk:
                continue
            chunk_id = ulid.new().str
            zrb_print(
                stylize_muted(f"Vectorizing {relative_path} chunk {chunk_id}"),
                plain=True,
            )
            embedding_response = openai_client.embeddings.create(
                input=chunk, model=embedding_model_val
            )
            collection.upsert(
                ids=[chunk_id],
                embeddings=[embedding_response.data[0].embedding],
                documents=[chunk],
                metadatas={"file_path": relative_path, "file_id": file_id},
            )
    except Exception as e:
        zrb_print(stylize_error(f"Error processing {file_path}: {e}"), plain=True)


def _embed_query(
    openai_client: Any, query: str, embedding_model_val: str
) -> tuple[Any, dict[str, Any] | None]:
    """Embed the query string. Returns `(vector, None)` or `(None, error_dict)`."""
    zrb_print(stylize_muted("Vectorizing query"), plain=True)
    try:
        embedding_response = openai_client.embeddings.create(
            input=query, model=embedding_model_val
        )
        return embedding_response.data[0].embedding, None
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "Unauthorized" in error_msg:
            return None, {
                "error": f"Embedding API authentication failed: {e}. [SYSTEM SUGGESTION]: The 'api_key' is invalid. Ask the user to provide a valid API key and retry the query."
            }
        elif "429" in error_msg or "rate limit" in error_msg.lower():
            return None, {
                "error": f"Embedding API rate limit exceeded: {e}. [SYSTEM SUGGESTION]: Wait before retrying, or ask the user to check their API plan limits."
            }
        else:
            return None, {
                "error": f"Failed to generate query embedding: {e}. [SYSTEM SUGGESTION]: The 'embedding_model' name may be invalid or the provider unreachable. Ask the user to verify the model name and base_url, then retry."
            }


def _query_collection(
    collection: Any, query_vector: Any, max_result_count_val: int, vector_db_path: str
) -> dict[str, Any]:
    """Run the similarity search and return its results (or an error dict)."""
    zrb_print(stylize_muted("Searching documents"), plain=True)
    try:
        results = collection.query(
            query_embeddings=query_vector,
            n_results=max_result_count_val,
        )
        return {**dict(results), "content_is": UNTRUSTED_DATA_NOTE}
    except Exception as e:
        return {
            "error": f"Failed to search documents: {e}. [SYSTEM SUGGESTION]: Ask the user to delete the ChromaDB directory ('{vector_db_path}') to reset the collection. This will force re-indexing of all documents on the next query."
        }


def compute_file_hash(file_path: str) -> str:
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def load_hashes(file_path: str) -> dict:
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            CFG.LOGGER.error(f"Error loading hash file {file_path}: {e}")
    return {}


def save_hashes(file_path: str, hashes: dict):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(hashes, f)


def read_txt_content(file_path: str, file_reader: list[RAGFileReader]):
    for reader in file_reader:
        if reader.is_match(file_path):
            return reader.read(file_path)
    return read_file(file_path)
