"""RAG config: embedding model/API, chunk size, overlap, result count."""

from __future__ import annotations

from zrb.config.env_field import EnvField


class RAGMixin:
    ENV_PREFIX: str

    def __init__(self):
        self.DEFAULT_RAG_EMBEDDING_API_KEY: str = ""
        self.DEFAULT_RAG_EMBEDDING_BASE_URL: str = ""
        self.DEFAULT_RAG_EMBEDDING_MODEL: str = "text-embedding-ada-002"
        self.DEFAULT_RAG_CHUNK_SIZE: str = "1024"
        self.DEFAULT_RAG_OVERLAP: str = "128"
        self.DEFAULT_RAG_MAX_RESULT_COUNT: str = "5"
        super().__init__()

    RAG_EMBEDDING_API_KEY = EnvField(
        str,
        nullable=True,
        secret=True,
        doc="API key for the embedding model provider. Unset defers to the provider's own env var.",
    )

    RAG_EMBEDDING_BASE_URL = EnvField(
        str,
        nullable=True,
        doc="Base URL for the embedding model API endpoint. Unset uses the provider default.",
    )

    RAG_EMBEDDING_MODEL = EnvField(
        str, doc="Embedding model identifier used for RAG indexing and retrieval."
    )

    RAG_CHUNK_SIZE = EnvField(
        int, doc="Token count per document chunk when indexing documents for RAG."
    )

    RAG_OVERLAP = EnvField(
        int,
        doc="Token overlap between adjacent document chunks to preserve context at boundaries.",
    )

    RAG_MAX_RESULT_COUNT = EnvField(
        int, doc="Maximum number of retrieved chunks returned per RAG query."
    )
