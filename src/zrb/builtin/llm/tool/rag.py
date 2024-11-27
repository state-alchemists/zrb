import json
import os
import sys
from collections.abc import Callable, Iterable

import litellm

from zrb.config import (
    RAG_CHUNK_SIZE,
    RAG_EMBEDDING_MODEL,
    RAG_MAX_RESULT_COUNT,
    RAG_OVERLAP,
)
from zrb.util.cli.style import stylize_error, stylize_faint
from zrb.util.run import run_async

Document = str | Callable[[], str]
Documents = Callable[[], Iterable[Document]] | Iterable[Document]


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
    return create_rag(
        tool_name=tool_name,
        tool_description=tool_description,
        documents=get_rag_documents(os.path.expanduser(document_dir_path)),
        model=model,
        vector_db_path=vector_db_path,
        vector_db_collection=vector_db_collection,
        reset_db=get_rag_reset_db(
            document_dir_path=os.path.expanduser(document_dir_path),
            vector_db_path=os.path.expanduser(vector_db_path),
        ),
        chunk_size=chunk_size,
        overlap=overlap,
        max_result_count=max_result_count,
    )


def create_rag(
    tool_name: str,
    tool_description: str,
    documents: Documents = [],
    model: str = RAG_EMBEDDING_MODEL,
    vector_db_path: str = "./chroma",
    vector_db_collection: str = "documents",
    reset_db: Callable[[], bool] | bool = False,
    chunk_size: int = RAG_CHUNK_SIZE,
    overlap: int = RAG_OVERLAP,
    max_result_count: int = RAG_MAX_RESULT_COUNT,
) -> Callable[[str], str]:
    async def retrieve(query: str) -> str:
        import chromadb
        from chromadb.config import Settings

        is_db_exist = os.path.isdir(vector_db_path)
        client = chromadb.PersistentClient(
            path=vector_db_path, settings=Settings(allow_reset=True)
        )
        should_reset_db = (
            await run_async(reset_db()) if callable(reset_db) else reset_db
        )
        if (not is_db_exist) or should_reset_db:
            client.reset()
            collection = client.get_or_create_collection(vector_db_collection)
            chunk_index = 0
            print(stylize_faint("Scanning documents"), file=sys.stderr)
            docs = await run_async(documents()) if callable(documents) else documents
            for document in docs:
                if callable(document):
                    try:
                        document = await run_async(document())
                    except Exception as error:
                        print(stylize_error(f"Error: {error}"), file=sys.stderr)
                        continue
                for i in range(0, len(document), chunk_size - overlap):
                    chunk = document[i : i + chunk_size]
                    if len(chunk) > 0:
                        print(
                            stylize_faint(f"Vectorize chunk {chunk_index}"),
                            file=sys.stderr,
                        )
                        response = await litellm.aembedding(model=model, input=[chunk])
                        vector = response["data"][0]["embedding"]
                        print(
                            stylize_faint(f"Adding chunk {chunk_index} to db"),
                            file=sys.stderr,
                        )
                        collection.upsert(
                            ids=[f"id{chunk_index}"],
                            embeddings=[vector],
                            documents=[chunk],
                        )
                        chunk_index += 1
        collection = client.get_or_create_collection(vector_db_collection)
        # Generate embedding for the query
        print(stylize_faint("Vectorize query"), file=sys.stderr)
        query_response = await litellm.aembedding(model=model, input=[query])
        print(stylize_faint("Search documents"), file=sys.stderr)
        # Search for the top_k most similar documents
        results = collection.query(
            query_embeddings=query_response["data"][0]["embedding"],
            n_results=max_result_count,
        )
        return json.dumps(results)

    retrieve.__name__ = tool_name
    retrieve.__doc__ = tool_description
    return retrieve


def get_rag_documents(document_dir_path: str) -> Callable[[], list[Callable[[], str]]]:
    def get_documents() -> list[Callable[[], str]]:
        # Walk through the directory
        readers = []
        for root, _, files in os.walk(document_dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                if file_path.lower().endswith(".pdf"):
                    readers.append(_get_pdf_reader(file_path))
                    continue
                readers.append(_get_text_reader(file_path))
        return readers

    return get_documents


def _get_text_reader(file_path: str):
    def read():
        print(stylize_faint(f"Start reading {file_path}"), file=sys.stderr)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        print(stylize_faint(f"Complete reading {file_path}"), file=sys.stderr)
        return content

    return read


def _get_pdf_reader(file_path):
    def read():
        import pdfplumber

        print(stylize_faint(f"Start reading {file_path}"), file=sys.stderr)
        contents = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                contents.append(page.extract_text())
        print(stylize_faint(f"Complete reading {file_path}"), file=sys.stderr)
        return "\n".join(contents)

    return read


def get_rag_reset_db(
    document_dir_path: str, vector_db_path: str = "./chroma"
) -> Callable[[], bool]:
    def should_reset_db() -> bool:
        document_exist = os.path.isdir(document_dir_path)
        if not document_exist:
            raise ValueError(f"Document directory not exists: {document_dir_path}")
        vector_db_exist = os.path.isdir(vector_db_path)
        if not vector_db_exist:
            return True
        document_mtime = _get_most_recent_mtime(document_dir_path)
        vector_db_mtime = _get_most_recent_mtime(vector_db_path)
        return document_mtime > vector_db_mtime

    return should_reset_db


def _get_most_recent_mtime(directory):
    most_recent_mtime = 0
    for root, dirs, files in os.walk(directory):
        # Check mtime for directories
        for name in dirs + files:
            file_path = os.path.join(root, name)
            mtime = os.path.getmtime(file_path)
            if mtime > most_recent_mtime:
                most_recent_mtime = mtime
    return most_recent_mtime
