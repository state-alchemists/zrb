import os

from zrb.config.config import Config
from zrb.config.helper import get_current_shell


def test_llm_model(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_MODEL", "my-model")
    config = Config()
    assert config.LLM_MODEL == "my-model"


def test_llm_model_none(monkeypatch):
    monkeypatch.delenv("ZRB_LLM_MODEL", raising=False)
    config = Config()
    assert config.LLM_MODEL is None


def test_llm_base_url(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_BASE_URL", "http://localhost:8080")
    config = Config()
    assert config.LLM_BASE_URL == "http://localhost:8080"


def test_llm_api_key(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_API_KEY", "my-api-key")
    config = Config()
    assert config.LLM_API_KEY == "my-api-key"


def test_llm_api_key_none(monkeypatch):
    monkeypatch.delenv("ZRB_LLM_API_KEY", raising=False)
    config = Config()
    assert config.LLM_API_KEY is None


def test_llm_max_request_per_minute(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_MAX_REQUEST_PER_MINUTE", "30")
    config = Config()
    assert config.LLM_MAX_REQUEST_PER_MINUTE == 30


def test_llm_max_request_per_minute_none(monkeypatch):
    monkeypatch.delenv("ZRB_LLM_MAX_REQUEST_PER_MINUTE", raising=False)
    config = Config()
    assert config.LLM_MAX_REQUEST_PER_MINUTE == 60


def test_llm_max_token_per_minute(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_MAX_TOKEN_PER_MINUTE", "200000")
    config = Config()
    assert config.LLM_MAX_TOKEN_PER_MINUTE == 200000


def test_llm_max_token_per_request(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_MAX_TOKEN_PER_REQUEST", "100000")
    config = Config()
    assert config.LLM_MAX_TOKEN_PER_REQUEST == 100000


def test_llm_throttle_sleep(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_THROTTLE_SLEEP", "2.0")
    config = Config()
    assert config.LLM_THROTTLE_SLEEP == 2.0


def test_llm_conversational_summarization_token_threshold(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD", "30000")
    config = Config()
    assert config.LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD == 30000


def test_llm_repo_analysis_extraction_token_threshold(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD", "40000")
    config = Config()
    assert config.LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD == 40000


def test_llm_repo_analysis_summarization_token_threshold(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD", "40000")
    config = Config()
    assert config.LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD == 40000


def test_llm_file_analysis_token_threshold(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_FILE_ANALYSIS_TOKEN_THRESHOLD", "40000")
    config = Config()
    assert config.LLM_FILE_ANALYSIS_TOKEN_THRESHOLD == 40000


def test_llm_configs_types():
    # Access all LLM properties to ensure coverage
    config = Config()
    assert config.LLM_MODEL is None or isinstance(config.LLM_MODEL, str)
    assert config.LLM_BASE_URL is None or isinstance(config.LLM_BASE_URL, str)
    assert config.LLM_API_KEY is None or isinstance(config.LLM_API_KEY, str)

    assert isinstance(config.LLM_MAX_REQUEST_PER_MINUTE, int)
    assert isinstance(config.LLM_MAX_TOKEN_PER_MINUTE, int)
    assert isinstance(config.LLM_MAX_TOKEN_PER_REQUEST, int)
    assert isinstance(config.LLM_THROTTLE_SLEEP, float)

    assert isinstance(config.LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD, int)
    assert isinstance(config.LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD, int)
    assert isinstance(config.LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD, int)
    assert isinstance(config.LLM_FILE_ANALYSIS_TOKEN_THRESHOLD, int)

    assert config.RAG_EMBEDDING_API_KEY is None or isinstance(
        config.RAG_EMBEDDING_API_KEY, str
    )
    assert config.RAG_EMBEDDING_BASE_URL is None or isinstance(
        config.RAG_EMBEDDING_BASE_URL, str
    )
    assert isinstance(config.RAG_EMBEDDING_MODEL, str)
    assert isinstance(config.RAG_CHUNK_SIZE, int)
    assert isinstance(config.RAG_OVERLAP, int)
    assert isinstance(config.RAG_MAX_RESULT_COUNT, int)

    assert isinstance(config.SEARCH_INTERNET_METHOD, str)
    assert isinstance(config.BRAVE_API_KEY, str)
    assert isinstance(config.BRAVE_API_SAFE, str)
    assert isinstance(config.BRAVE_API_LANG, str)
    assert isinstance(config.SERPAPI_KEY, str)
    assert isinstance(config.SERPAPI_SAFE, str)
    assert isinstance(config.SERPAPI_LANG, str)

    assert isinstance(config.SEARXNG_PORT, int)
    assert isinstance(config.SEARXNG_BASE_URL, str)
    assert isinstance(config.SEARXNG_SAFE, int)
    assert isinstance(config.SEARXNG_LANG, str)

    assert isinstance(config.BANNER, str)
    assert isinstance(config.USE_TIKTOKEN, bool)
    assert isinstance(config.TIKTOKEN_ENCODING_NAME, str)


def test_llm_plugin_dirs(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_PLUGIN_DIRS", "dir1:dir2")
    config = Config()
    assert config.LLM_PLUGIN_DIRS == ["dir1", "dir2"]


def test_llm_plugin_dirs_tilde_expansion(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_PLUGIN_DIRS", "~/.bsim-ai-workflow")
    config = Config()
    result = config.LLM_PLUGIN_DIRS
    assert len(result) == 1
    assert result[0] == os.path.expanduser("~/.bsim-ai-workflow")
    assert "~" not in result[0]


def test_llm_small_model(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_SMALL_MODEL", "gpt-4o-mini")
    config = Config()
    assert (
        config.SHELL == get_current_shell()
    )  # Existing test was slightly wrong in my previous read, it seems config.SHELL defaults to get_current_shell() on Linux/Darwin
    assert config.LLM_SMALL_MODEL == "gpt-4o-mini"
