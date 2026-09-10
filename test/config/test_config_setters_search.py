import os

from zrb.config.config import Config


class TestSearchConfigSetters:
    """Test Config property setters by verifying they write to os.environ."""

    _original_env: dict[str, str] = {}

    def test_rag_embedding_api_key_setter_with_value(self, monkeypatch):
        config = Config()
        config.RAG_EMBEDDING_API_KEY = "rag-key"
        assert os.environ["ZRB_RAG_EMBEDDING_API_KEY"] == "rag-key"

    def test_rag_embedding_api_key_setter_with_none(self, monkeypatch):
        config = Config()
        config.RAG_EMBEDDING_API_KEY = "rag-key"
        config.RAG_EMBEDDING_API_KEY = None
        assert "ZRB_RAG_EMBEDDING_API_KEY" not in os.environ

    def test_rag_embedding_base_url_setter_with_value(self, monkeypatch):
        config = Config()
        config.RAG_EMBEDDING_BASE_URL = "http://localhost:8081"
        assert os.environ["ZRB_RAG_EMBEDDING_BASE_URL"] == "http://localhost:8081"

    def test_rag_embedding_base_url_setter_with_none(self, monkeypatch):
        config = Config()
        config.RAG_EMBEDDING_BASE_URL = "http://localhost:8081"
        config.RAG_EMBEDDING_BASE_URL = None
        assert "ZRB_RAG_EMBEDDING_BASE_URL" not in os.environ

    def test_rag_embedding_model_setter(self, monkeypatch):
        config = Config()
        config.RAG_EMBEDDING_MODEL = "text-embedding-3-small"
        assert os.environ["ZRB_RAG_EMBEDDING_MODEL"] == "text-embedding-3-small"

    def test_rag_chunk_size_setter(self, monkeypatch):
        config = Config()
        config.RAG_CHUNK_SIZE = 2048
        assert os.environ["ZRB_RAG_CHUNK_SIZE"] == "2048"

    def test_rag_overlap_setter(self, monkeypatch):
        config = Config()
        config.RAG_OVERLAP = 256
        assert os.environ["ZRB_RAG_OVERLAP"] == "256"

    def test_rag_max_result_count_setter(self, monkeypatch):
        config = Config()
        config.RAG_MAX_RESULT_COUNT = 10
        assert os.environ["ZRB_RAG_MAX_RESULT_COUNT"] == "10"

    def test_search_internet_method_setter(self, monkeypatch):
        config = Config()
        config.SEARCH_INTERNET_METHOD = "searxng"
        assert os.environ["ZRB_SEARCH_INTERNET_METHOD"] == "searxng"

    def test_brave_api_key_setter(self, monkeypatch):
        config = Config()
        config.BRAVE_API_KEY = "brave-key"
        assert os.environ["BRAVE_API_KEY"] == "brave-key"

    def test_brave_api_safe_setter(self, monkeypatch):
        config = Config()
        config.BRAVE_API_SAFE = "on"
        assert os.environ["ZRB_BRAVE_API_SAFE"] == "on"

    def test_brave_api_lang_setter(self, monkeypatch):
        config = Config()
        config.BRAVE_API_LANG = "en"
        assert os.environ["ZRB_BRAVE_API_LANG"] == "en"

    def test_serpapi_key_setter(self, monkeypatch):
        config = Config()
        config.SERPAPI_KEY = "serp-key"
        assert os.environ["SERPAPI_KEY"] == "serp-key"

    def test_serpapi_safe_setter(self, monkeypatch):
        config = Config()
        config.SERPAPI_SAFE = "on"
        assert os.environ["ZRB_SERPAPI_SAFE"] == "on"

    def test_serpapi_lang_setter(self, monkeypatch):
        config = Config()
        config.SERPAPI_LANG = "en"
        assert os.environ["ZRB_SERPAPI_LANG"] == "en"

    def test_searxng_port_setter(self, monkeypatch):
        config = Config()
        config.SEARXNG_PORT = 9090
        assert os.environ["ZRB_SEARXNG_PORT"] == "9090"

    def test_searxng_base_url_setter(self, monkeypatch):
        config = Config()
        config.SEARXNG_BASE_URL = "http://searxng:8080"
        assert os.environ["ZRB_SEARXNG_BASE_URL"] == "http://searxng:8080"

    def test_searxng_safe_setter(self, monkeypatch):
        config = Config()
        config.SEARXNG_SAFE = 1
        assert os.environ["ZRB_SEARXNG_SAFE"] == "1"

    def test_searxng_lang_setter(self, monkeypatch):
        config = Config()
        config.SEARXNG_LANG = "en-US"
        assert os.environ["ZRB_SEARXNG_LANG"] == "en-US"
