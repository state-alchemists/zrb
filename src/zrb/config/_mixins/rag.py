"""RAG config: embedding model/API, chunk size, overlap, result count."""

from __future__ import annotations

import os

from zrb.config.helper import get_env


class RAGMixin:
    def __init__(self):
        self.DEFAULT_RAG_EMBEDDING_API_KEY: str = ""
        self.DEFAULT_RAG_EMBEDDING_BASE_URL: str = ""
        self.DEFAULT_RAG_EMBEDDING_MODEL: str = "text-embedding-ada-002"
        self.DEFAULT_RAG_CHUNK_SIZE: str = "1024"
        self.DEFAULT_RAG_OVERLAP: str = "128"
        self.DEFAULT_RAG_MAX_RESULT_COUNT: str = "5"
        super().__init__()

    @property
    def RAG_EMBEDDING_API_KEY(self) -> str | None:
        value = get_env(
            "RAG_EMBEDDING_API_KEY",
            self.DEFAULT_RAG_EMBEDDING_API_KEY,
            self.ENV_PREFIX,
        )
        return None if value == "" else value

    @RAG_EMBEDDING_API_KEY.setter
    def RAG_EMBEDDING_API_KEY(self, value: str | None):
        if value is None:
            if f"{self.ENV_PREFIX}_RAG_EMBEDDING_API_KEY" in os.environ:
                del os.environ[f"{self.ENV_PREFIX}_RAG_EMBEDDING_API_KEY"]
        else:
            os.environ[f"{self.ENV_PREFIX}_RAG_EMBEDDING_API_KEY"] = value

    @property
    def RAG_EMBEDDING_BASE_URL(self) -> str | None:
        value = get_env(
            "RAG_EMBEDDING_BASE_URL",
            self.DEFAULT_RAG_EMBEDDING_BASE_URL,
            self.ENV_PREFIX,
        )
        return None if value == "" else value

    @RAG_EMBEDDING_BASE_URL.setter
    def RAG_EMBEDDING_BASE_URL(self, value: str | None):
        if value is None:
            if f"{self.ENV_PREFIX}_RAG_EMBEDDING_BASE_URL" in os.environ:
                del os.environ[f"{self.ENV_PREFIX}_RAG_EMBEDDING_BASE_URL"]
        else:
            os.environ[f"{self.ENV_PREFIX}_RAG_EMBEDDING_BASE_URL"] = value

    @property
    def RAG_EMBEDDING_MODEL(self) -> str:
        return get_env(
            "RAG_EMBEDDING_MODEL", self.DEFAULT_RAG_EMBEDDING_MODEL, self.ENV_PREFIX
        )

    @RAG_EMBEDDING_MODEL.setter
    def RAG_EMBEDDING_MODEL(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_RAG_EMBEDDING_MODEL"] = value

    @property
    def RAG_CHUNK_SIZE(self) -> int:
        return int(
            get_env("RAG_CHUNK_SIZE", self.DEFAULT_RAG_CHUNK_SIZE, self.ENV_PREFIX)
        )

    @RAG_CHUNK_SIZE.setter
    def RAG_CHUNK_SIZE(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_RAG_CHUNK_SIZE"] = str(value)

    @property
    def RAG_OVERLAP(self) -> int:
        return int(get_env("RAG_OVERLAP", self.DEFAULT_RAG_OVERLAP, self.ENV_PREFIX))

    @RAG_OVERLAP.setter
    def RAG_OVERLAP(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_RAG_OVERLAP"] = str(value)

    @property
    def RAG_MAX_RESULT_COUNT(self) -> int:
        return int(
            get_env(
                "RAG_MAX_RESULT_COUNT",
                self.DEFAULT_RAG_MAX_RESULT_COUNT,
                self.ENV_PREFIX,
            )
        )

    @RAG_MAX_RESULT_COUNT.setter
    def RAG_MAX_RESULT_COUNT(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_RAG_MAX_RESULT_COUNT"] = str(value)
