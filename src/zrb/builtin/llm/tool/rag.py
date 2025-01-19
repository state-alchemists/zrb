import hashlib
import json
import os
import sys

import ulid

from zrb.config import (
    RAG_CHUNK_SIZE,
    RAG_EMBEDDING_MODEL,
    RAG_MAX_RESULT_COUNT,
    RAG_OVERLAP,
)
from zrb.util.cli.style import stylize_error, stylize_faint
from zrb.util.file import read_file


def create_rag_from_directory(
    tool_name: str,
    tool_description: str,
    document_dir_path: str = "./documents",
    model: str = RAG_EMBEDDING_MODEL,
    vector_db_path: str = "./chroma",
    vector_db_collection: str = "documents",
    chunk_size: int = RAG_CHUNK_SIZE,
    overlap: int = RAG_OVERLAP,
    max_result_count: int = RAG_MAX_RESULT_COUNT,
):
    async def retrieve(query: str) -> str:
        from chromadb import PersistentClient
        from chromadb.config import Settings
        from fastembed import TextEmbedding

        embedding_model = TextEmbedding(model_name=model)
        client = PersistentClient(
            path=vector_db_path, settings=Settings(allow_reset=True)
        )
        collection = client.get_or_create_collection(vector_db_collection)

        # Track file changes using a hash-based approach
        hash_file_path = os.path.join(vector_db_path, "file_hashes.json")
        previous_hashes = _load_hashes(hash_file_path)
        current_hashes = {}

        updated_files = []

        for root, _, files in os.walk(document_dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                file_hash = _compute_file_hash(file_path)
                relative_path = os.path.relpath(file_path, document_dir_path)
                current_hashes[relative_path] = file_hash

                if previous_hashes.get(relative_path) != file_hash:
                    updated_files.append(file_path)

        if updated_files:
            print(
                stylize_faint(f"Updating {len(updated_files)} changed files"),
                file=sys.stderr,
            )

            for file_path in updated_files:
                try:
                    relative_path = os.path.relpath(file_path, document_dir_path)
                    collection.delete(where={"file_path": relative_path})
                    content = _read_file_content(file_path)
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
                            embedding_result = list(embedding_model.embed([chunk]))
                            vector = embedding_result[0]
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

        print(stylize_faint("Vectorizing query"), file=sys.stderr)
        embedding_result = list(embedding_model.embed([query]))
        query_vector = embedding_result[0]
        print(stylize_faint("Searching documents"), file=sys.stderr)
        results = collection.query(
            query_embeddings=query_vector,
            n_results=max_result_count,
        )
        return json.dumps(results)

    retrieve.__name__ = tool_name
    retrieve.__doc__ = tool_description
    return retrieve


def _compute_file_hash(file_path: str) -> str:
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def _read_file_content(file_path: str) -> str:
    if file_path.lower().endswith(".pdf"):
        return _read_pdf(file_path)
    return read_file(file_path)


def _read_pdf(file_path: str) -> str:
    import pdfplumber

    with pdfplumber.open(file_path) as pdf:
        return "\n".join(
            page.extract_text() for page in pdf.pages if page.extract_text()
        )


def _load_hashes(file_path: str) -> dict:
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return {}


def _save_hashes(file_path: str, hashes: dict):
    with open(file_path, "w") as f:
        json.dump(hashes, f)
