import fnmatch
import hashlib
import json
import os
from collections.abc import Callable
from textwrap import dedent
from typing import Any

import ulid

from zrb.config.config import CFG
from zrb.context.any_context import zrb_print
from zrb.util.cli.style import stylize_error, stylize_faint
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


def create_rag_from_directory(
    tool_name: str,
    tool_description: str,
    document_dir_path: str = "./documents",
    vector_db_path: str = "./chroma",
    vector_db_collection: str = "documents",
    chunk_size: int | None = None,
    overlap: int | None = None,
    max_result_count: int | None = None,
    file_reader: list[RAGFileReader] = [],
    model_api_key: str | None = None,
    model_base_url: str | None = None,
    model_name: str | None = None,
):
    """
    Create a powerful RAG (Retrieval-Augmented Generation) tool for querying a local
    knowledge base.

    This factory function generates a tool that performs semantic search over a directory of
    documents. It automatically indexes the documents into a vector database (ChromaDB) and
    keeps it updated as files change.

    The generated tool is ideal for answering questions based on a specific set of documents,
    such as project documentation or internal wikis.

    Args:
        tool_name (str): The name for the generated RAG tool (e.g., "search_project_docs").
        tool_description (str): A clear description of what the tool does and when to use it.
            This is what the LLM will see.
        document_dir_path (str, optional): The path to the directory containing the documents
            to be indexed.
        vector_db_path (str, optional): The path where the ChromaDB vector database will be
            stored.
        vector_db_collection (str, optional): The name of the collection within the vector
            database.
        chunk_size (int, optional): The size of text chunks for embedding.
        overlap (int, optional): The overlap between text chunks.
        max_result_count (int, optional): The maximum number of search results to return.
        file_reader (list[RAGFileReader], optional): A list of custom file readers for
            specific file types.
        model_api_key (str, optional): Your API key for generating embeddings.
        model_base_url (str, optional): An optional base URL for the OpenAI API.
        model_name (str, optional): The embedding model to use.

    Returns:
        An asynchronous function that serves as the RAG tool.
    """

    async def retrieve(
        query: str,
        api_key: str | None = None,
        base_url: str | None = None,
        embedding_model: str | None = None,
    ) -> dict[str, Any]:
        try:
            from chromadb import PersistentClient
            from chromadb.config import Settings
            from openai import OpenAI
        except ImportError as e:
            return {
                "error": f"Missing required dependency: {e}. [SYSTEM SUGGESTION]: Ask the user to install the required packages: pip install chromadb openai"
            }

        api_key_val = (
            api_key
            if api_key is not None
            else (
                model_api_key
                if model_api_key is not None
                else CFG.RAG_EMBEDDING_API_KEY
            )
        )
        base_url_val = (
            base_url
            if base_url is not None
            else (
                model_base_url
                if model_base_url is not None
                else CFG.RAG_EMBEDDING_BASE_URL
            )
        )
        embedding_model_val = (
            embedding_model
            if embedding_model is not None
            else model_name if model_name is not None else CFG.RAG_EMBEDDING_MODEL
        )
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

        client_args = {"api_key": api_key_val}
        if base_url_val:
            client_args["base_url"] = base_url_val

        try:
            openai_client = OpenAI(**client_args)
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
        try:
            previous_hashes = _load_hashes(hash_file_path)
        except Exception as e:
            zrb_print(stylize_error(f"Error loading file hashes: {e}"), plain=True)
            previous_hashes = {}

        current_hashes = {}
        updated_files = []

        if not os.path.exists(document_dir_path):
            return {
                "error": f"Document directory not found: {document_dir_path}. [SYSTEM SUGGESTION]: Ask the user to verify the document_dir_path. The directory may have been moved, deleted, or the path may be wrong."
            }

        for root, _, files in os.walk(document_dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    file_hash = _compute_file_hash(file_path)
                    relative_path = os.path.relpath(file_path, document_dir_path)
                    current_hashes[relative_path] = file_hash
                    if previous_hashes.get(relative_path) != file_hash:
                        updated_files.append(file_path)
                except Exception as e:
                    zrb_print(
                        stylize_error(f"Error hashing file {file_path}: {e}"),
                        plain=True,
                    )

        if updated_files:
            zrb_print(
                stylize_faint(f"Updating {len(updated_files)} changed files"),
                plain=True,
            )
            for file_path in updated_files:
                try:
                    relative_path = os.path.relpath(file_path, document_dir_path)
                    collection.delete(where={"file_path": relative_path})
                    content = _read_txt_content(file_path, file_reader)
                    file_id = ulid.new().str
                    for i in range(0, len(content), chunk_size_val - overlap_val):
                        chunk = content[i : i + chunk_size_val]
                        if chunk:
                            chunk_id = ulid.new().str
                            zrb_print(
                                stylize_faint(
                                    f"Vectorizing {relative_path} chunk {chunk_id}"
                                ),
                                plain=True,
                            )
                            embedding_response = openai_client.embeddings.create(
                                input=chunk, model=embedding_model_val
                            )
                            vector = embedding_response.data[0].embedding
                            collection.upsert(
                                ids=[chunk_id],
                                embeddings=[vector],
                                documents=[chunk],
                                metadatas={
                                    "file_path": relative_path,
                                    "file_id": file_id,
                                },
                            )
                except Exception as e:
                    zrb_print(
                        stylize_error(f"Error processing {file_path}: {e}"), plain=True
                    )
            _save_hashes(hash_file_path, current_hashes)
        else:
            zrb_print(
                stylize_faint("No changes detected. Skipping database update."),
                plain=True,
            )

        zrb_print(stylize_faint("Vectorizing query"), plain=True)

        try:
            embedding_response = openai_client.embeddings.create(
                input=query, model=embedding_model_val
            )
            query_vector = embedding_response.data[0].embedding
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "Unauthorized" in error_msg:
                return {
                    "error": f"Embedding API authentication failed: {e}. [SYSTEM SUGGESTION]: The 'api_key' is invalid. Ask the user to provide a valid API key and retry the query."
                }
            elif "429" in error_msg or "rate limit" in error_msg.lower():
                return {
                    "error": f"Embedding API rate limit exceeded: {e}. [SYSTEM SUGGESTION]: Wait before retrying, or ask the user to check their API plan limits."
                }
            else:
                return {
                    "error": f"Failed to generate query embedding: {e}. [SYSTEM SUGGESTION]: The 'embedding_model' name may be invalid or the provider unreachable. Ask the user to verify the model name and base_url, then retry."
                }

        zrb_print(stylize_faint("Searching documents"), plain=True)

        try:
            results = collection.query(
                query_embeddings=query_vector,
                n_results=max_result_count_val,
            )
            return dict(results)
        except Exception as e:
            return {
                "error": f"Failed to search documents: {e}. [SYSTEM SUGGESTION]: Ask the user to delete the ChromaDB directory ('{vector_db_path}') to reset the collection. This will force re-indexing of all documents on the next query."
            }

    retrieve.__name__ = tool_name
    retrieve.__doc__ = dedent(f"""
        {tool_description}
        This tool performs a semantic search across a curated knowledge base of documents.
        It is highly effective for answering questions that require specific project knowledge not found in general training data.

        **ARGS:**
        - `query` (str): The semantic search query or question.
        - `api_key` (str, optional): Embedding API key. Falls back to tool default or CFG.RAG_EMBEDDING_API_KEY.
        - `base_url` (str, optional): Embedding API base URL. Falls back to tool default or CFG.RAG_EMBEDDING_BASE_URL.
        - `embedding_model` (str, optional): Embedding model name. Falls back to tool default or CFG.RAG_EMBEDDING_MODEL.

        **RETURNS:**
        - A dictionary containing matching document chunks ("documents") and their metadata.
        """).strip()
    return retrieve


def _compute_file_hash(file_path: str) -> str:
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def _load_hashes(file_path: str) -> dict:
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_hashes(file_path: str, hashes: dict):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(hashes, f)


def _read_txt_content(file_path: str, file_reader: list[RAGFileReader]):
    for reader in file_reader:
        if reader.is_match(file_path):
            return reader.read(file_path)
    return read_file(file_path)
