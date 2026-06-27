from zrb.config.config import Config


def test_rag_embedding_api_key(monkeypatch):
    monkeypatch.setenv("ZRB_RAG_EMBEDDING_API_KEY", "my-rag-api-key")
    config = Config()
    assert config.RAG_EMBEDDING_API_KEY == "my-rag-api-key"


def test_rag_embedding_base_url(monkeypatch):
    monkeypatch.setenv("ZRB_RAG_EMBEDDING_BASE_URL", "http://localhost:8081")
    config = Config()
    assert config.RAG_EMBEDDING_BASE_URL == "http://localhost:8081"


def test_rag_embedding_model(monkeypatch):
    monkeypatch.setenv("ZRB_RAG_EMBEDDING_MODEL", "my-embedding-model")
    config = Config()
    assert config.RAG_EMBEDDING_MODEL == "my-embedding-model"


def test_rag_chunk_size(monkeypatch):
    monkeypatch.setenv("ZRB_RAG_CHUNK_SIZE", "2048")
    config = Config()
    assert config.RAG_CHUNK_SIZE == 2048


def test_rag_overlap(monkeypatch):
    monkeypatch.setenv("ZRB_RAG_OVERLAP", "256")
    config = Config()
    assert config.RAG_OVERLAP == 256


def test_rag_max_result_count(monkeypatch):
    monkeypatch.setenv("ZRB_RAG_MAX_RESULT_COUNT", "10")
    config = Config()
    assert config.RAG_MAX_RESULT_COUNT == 10


def test_serpapi_key(monkeypatch):
    monkeypatch.setenv("SERPAPI_KEY", "my-serpapi-key")
    config = Config()
    assert config.SERPAPI_KEY == "my-serpapi-key"
