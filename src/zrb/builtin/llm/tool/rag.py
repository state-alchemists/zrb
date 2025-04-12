import fnmatch
import hashlib
import json
import os
import sys
from collections.abc import Callable
from textwrap import dedent

import ulid

from zrb.config import (
    RAG_CHUNK_SIZE,
    RAG_EMBEDDING_API_KEY,
    RAG_EMBEDDING_BASE_URL,
    RAG_EMBEDDING_MODEL,
    RAG_MAX_RESULT_COUNT,
    RAG_OVERLAP,
)
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
    chunk_size: int = RAG_CHUNK_SIZE,
    overlap: int = RAG_OVERLAP,
    max_result_count: int = RAG_MAX_RESULT_COUNT,
    file_reader: list[RAGFileReader] = [],
    openai_api_key: str = RAG_EMBEDDING_API_KEY,
    openai_base_url: str = RAG_EMBEDDING_BASE_URL,
    openai_embedding_model: str = RAG_EMBEDDING_MODEL,
):
    """Create a RAG retrieval tool function for LLM use.
    This factory configures and returns an async function that takes a query,
    updates a vector database if needed, performs a similarity search,
    and returns relevant document chunks.
    """

    async def retrieve(query: str) -> str:
        # Docstring will be set dynamically below
        from chromadb import PersistentClient
        from chromadb.config import Settings
        from openai import OpenAI

        # Initialize OpenAI client with custom URL if provided
        client_args = {}
        if openai_api_key:
            client_args["api_key"] = openai_api_key
        if openai_base_url:
            client_args["base_url"] = openai_base_url
        # Initialize OpenAI client for embeddings
        openai_client = OpenAI(**client_args)
        # Initialize ChromaDB client
        chroma_client = PersistentClient(
            path=vector_db_path, settings=Settings(allow_reset=True)
        )
        collection = chroma_client.get_or_create_collection(vector_db_collection)
        # Track file changes using a hash-based approach
        hash_file_path = os.path.join(vector_db_path, "file_hashes.json")
        previous_hashes = _load_hashes(hash_file_path)
        current_hashes = {}
        # Get updated_files
        updated_files = []
        for root, _, files in os.walk(document_dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                file_hash = _compute_file_hash(file_path)
                relative_path = os.path.relpath(file_path, document_dir_path)
                current_hashes[relative_path] = file_hash
                if previous_hashes.get(relative_path) != file_hash:
                    updated_files.append(file_path)
        # Upsert updated_files to vector db
        if updated_files:
            print(
                stylize_faint(f"Updating {len(updated_files)} changed files"),
                file=sys.stderr,
            )
            for file_path in updated_files:
                try:
                    relative_path = os.path.relpath(file_path, document_dir_path)
                    collection.delete(where={"file_path": relative_path})
                    content = _read_txt_content(file_path, file_reader)
                    file_id = ulid.new().str
                    for i in range(0, len(content), chunk_size - overlap):
                        chunk = content[i : i + chunk_size]
                        if chunk:
                            chunk_id = ulid.new().str
                            print(
                                stylize_faint(
                                    f"Vectorizing {relative_path} chunk {chunk_id}"
                                ),
                                file=sys.stderr,
                            )
                            # Get embeddings using OpenAI
                            embedding_response = openai_client.embeddings.create(
                                input=chunk, model=openai_embedding_model
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
                    print(
                        stylize_error(f"Error processing {file_path}: {e}"),
                        file=sys.stderr,
                    )
            _save_hashes(hash_file_path, current_hashes)
        else:
            print(
                stylize_faint("No changes detected. Skipping database update."),
                file=sys.stderr,
            )
        # Vectorize query and get related document chunks
        print(stylize_faint("Vectorizing query"), file=sys.stderr)
        # Get embeddings using OpenAI
        embedding_response = openai_client.embeddings.create(
            input=query, model=openai_embedding_model
        )
        query_vector = embedding_response.data[0].embedding
        print(stylize_faint("Searching documents"), file=sys.stderr)
        results = collection.query(
            query_embeddings=query_vector,
            n_results=max_result_count,
        )
        return json.dumps(results)

    retrieve.__name__ = tool_name
    retrieve.__doc__ = dedent(
        f"""{tool_description}
        Args:
            query (str): The user query to search for in documents.
        Returns:
            str: JSON string with search results: {{"ids": [...], "documents": [...], ...}}
    """
    )
    return retrieve


def _compute_file_hash(file_path: str) -> str:
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def _load_hashes(file_path: str) -> dict:
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return {}


def _save_hashes(file_path: str, hashes: dict):
    with open(file_path, "w") as f:
        json.dump(hashes, f)


def _read_txt_content(file_path: str, file_reader: list[RAGFileReader]):
    for reader in file_reader:
        if reader.is_match(file_path):
            return reader.read(file_path)
    if file_path.lower().endswith(".pdf"):
        return _read_pdf(file_path)
    return read_file(file_path)


def _read_pdf(file_path: str) -> str:
    import pdfplumber

    with pdfplumber.open(file_path) as pdf:
        return "\n".join(
            page.extract_text() for page in pdf.pages if page.extract_text()
        )
