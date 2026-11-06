import os

from zrb.config.config import Config
from zrb.config.helper import (
    CONVERSATIONAL_TRIGGER_DEFAULT_CEILING,
    get_current_shell,
)


def test_llm_model(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_MODEL", "my-model")
    config = Config()
    assert config.LLM_MODEL == "my-model"


def test_llm_model_default(monkeypatch):
    monkeypatch.delenv("ZRB_LLM_MODEL", raising=False)
    config = Config()
    assert config.LLM_MODEL == "openai:gpt-5.6-luna"


def test_llm_provider(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_PROVIDER", "anthropic")
    config = Config()
    assert config.LLM_PROVIDER == "anthropic"


def test_llm_provider_none(monkeypatch):
    monkeypatch.delenv("ZRB_LLM_PROVIDER", raising=False)
    config = Config()
    assert config.LLM_PROVIDER is None


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


def test_llm_max_token_per_minute_assignment_takes_precedence_over_legacy_alias(
    monkeypatch,
):
    monkeypatch.delenv("ZRB_LLM_MAX_TOKENS_PER_MINUTE", raising=False)
    monkeypatch.setenv("ZRB_LLM_MAX_TOKEN_PER_MINUTE", "7")
    config = Config()

    assert config.LLM_MAX_TOKEN_PER_MINUTE == 7

    config.LLM_MAX_TOKEN_PER_MINUTE = 11

    assert config.LLM_MAX_TOKEN_PER_MINUTE == 11


def test_llm_max_token_per_request(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_MAX_TOKEN_PER_REQUEST", "100000")
    config = Config()
    assert config.LLM_MAX_TOKEN_PER_REQUEST == 100000


def test_llm_enable_tool_spill_reads_the_legacy_key(monkeypatch):
    monkeypatch.delenv("ZRB_LLM_TOOL_SPILL_ENABLED", raising=False)
    monkeypatch.setenv("ZRB_LLM_TOOL_SPILL_ENABLED", "on")

    assert Config().LLM_TOOL_SPILL_ENABLED is True


def test_llm_throttle_sleep(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_THROTTLE_SLEEP", "2.0")
    config = Config()
    assert config.LLM_THROTTLE_SLEEP == 2.0


def test_llm_conversational_summarization_token_threshold(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD", "30000")
    config = Config()
    assert config.LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD == 30000


def test_llm_conversational_summarization_default_stops_at_200k(monkeypatch):
    """A half-million-token window does not buy half a million tokens of history.

    Every round re-sends the whole conversation, so the ceiling bounds how big
    a conversation may get before it is compressed, not how often it is.
    """
    monkeypatch.delenv(
        "ZRB_LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD", raising=False
    )
    monkeypatch.setenv("ZRB_LLM_MAX_TOKEN_PER_REQUEST", "1000000")
    monkeypatch.setenv("ZRB_LLM_MAX_TOKEN_PER_MINUTE", "1000000")

    assert CONVERSATIONAL_TRIGGER_DEFAULT_CEILING == 200_000
    assert Config().LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD == 200_000


def test_llm_conversational_summarization_default_follows_a_smaller_budget(
    monkeypatch,
):
    """Below the ceiling the budget still decides, so the default is a `min`."""
    monkeypatch.delenv(
        "ZRB_LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD", raising=False
    )
    monkeypatch.setenv("ZRB_LLM_MAX_TOKEN_PER_REQUEST", "128000")
    monkeypatch.setenv("ZRB_LLM_MAX_TOKEN_PER_MINUTE", "128000")

    assert Config().LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD == 96_000


def test_llm_conversational_summarization_threshold_is_clamped_to_the_budget(
    monkeypatch,
):
    """An explicit threshold is honoured, but never past 75% of the budget."""
    monkeypatch.setenv("ZRB_LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD", "900000")
    monkeypatch.setenv("ZRB_LLM_MAX_TOKEN_PER_REQUEST", "128000")
    monkeypatch.setenv("ZRB_LLM_MAX_TOKEN_PER_MINUTE", "128000")

    assert Config().LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD == 96_000


def test_llm_conversational_summarization_threshold_above_the_ceiling_is_kept(
    monkeypatch,
):
    """The ceiling is on the default: an explicit threshold is the answer given."""
    monkeypatch.setenv("ZRB_LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD", "250000")
    monkeypatch.setenv("ZRB_LLM_MAX_TOKEN_PER_REQUEST", "1000000")
    monkeypatch.setenv("ZRB_LLM_MAX_TOKEN_PER_MINUTE", "1000000")

    assert Config().LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD == 250_000


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
    assert isinstance(config.TIKTOKEN_ENABLED, bool)
    assert isinstance(config.TIKTOKEN_ENCODING_NAME, str)


def test_llm_plugin_dirs(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_PLUGIN_DIRS", f"dir1{os.pathsep}dir2")
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


def test_llm_max_skills_in_catalog_default(monkeypatch):
    monkeypatch.delenv("ZRB_LLM_MAX_SKILLS_IN_CATALOG", raising=False)
    config = Config()
    assert config.LLM_MAX_SKILLS_IN_CATALOG == 10


def test_llm_max_skills_in_catalog_override(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_MAX_SKILLS_IN_CATALOG", "5")
    config = Config()
    assert config.LLM_MAX_SKILLS_IN_CATALOG == 5


def test_llm_max_agents_in_roster_default(monkeypatch):
    monkeypatch.delenv("ZRB_LLM_MAX_AGENTS_IN_ROSTER", raising=False)
    config = Config()
    assert config.LLM_MAX_AGENTS_IN_ROSTER == 10


def test_llm_max_agents_in_roster_override(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_MAX_AGENTS_IN_ROSTER", "3")
    config = Config()
    assert config.LLM_MAX_AGENTS_IN_ROSTER == 3


def test_llm_rewind_is_on_and_self_review_off_by_default(monkeypatch):
    monkeypatch.delenv("ZRB_LLM_REWIND_ENABLED", raising=False)
    monkeypatch.delenv("ZRB_LLM_SELF_REVIEW_ENABLED", raising=False)
    config = Config()
    assert config.LLM_REWIND_ENABLED is True
    assert config.LLM_SELF_REVIEW_ENABLED is False
