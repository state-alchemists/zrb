import logging
import os
from unittest.mock import mock_open, patch

import pytest

from zrb.config.config import CFG, Config


def test_env_prefix():
    # Default
    config = Config()
    assert config.ENV_PREFIX == "ZRB"

    # Custom
    with patch.dict(os.environ, {"_ZRB_ENV_PREFIX": "MYAPP"}):
        assert config.ENV_PREFIX == "MYAPP"


def test_getenv_single():
    config = Config()
    # No env set, returns default
    assert config._getenv("TEST_VAR", "default") == "default"

    # Env set
    with patch.dict(os.environ, {"ZRB_TEST_VAR": "value"}):
        assert config._getenv("TEST_VAR", "default") == "value"


def test_getenv_list():
    config = Config()
    # First match
    with patch.dict(os.environ, {"ZRB_VAR1": "val1", "ZRB_VAR2": "val2"}):
        assert config._getenv(["VAR1", "VAR2"], "default") == "val1"

    # Second match
    with patch.dict(os.environ, {"ZRB_VAR2": "val2"}):
        assert config._getenv(["VAR1", "VAR2"], "default") == "val2"


def test_default_shell():
    config = Config()
    # MagicMock platform.system
    with patch("platform.system", return_value="Windows"):
        assert config.DEFAULT_SHELL == "PowerShell"

    with patch("platform.system", return_value="Linux"):
        with patch.dict(os.environ, {"SHELL": "/bin/zsh"}):
            assert config._get_current_shell() == "zsh"
        with patch.dict(os.environ, {"SHELL": "/bin/bash"}):
            assert config._get_current_shell() == "bash"


def test_diff_edit_command():
    config = Config()

    # Test vscode
    with patch.dict(os.environ, {"ZRB_EDITOR": "code"}):
        assert "code --wait" in config.DEFAULT_DIFF_EDIT_COMMAND_TPL

    # Test emacs
    with patch.dict(os.environ, {"ZRB_EDITOR": "emacs"}):
        assert "emacs --eval" in config.DEFAULT_DIFF_EDIT_COMMAND_TPL

    # Test vim
    with patch.dict(os.environ, {"ZRB_EDITOR": "vim"}):
        assert "vim -d" in config.DEFAULT_DIFF_EDIT_COMMAND_TPL

    # Test default (nano or unknown)
    with patch.dict(os.environ, {"ZRB_EDITOR": "nano"}):
        assert "vimdiff" in config.DEFAULT_DIFF_EDIT_COMMAND_TPL


def test_init_modules():
    config = Config()
    with patch.dict(os.environ, {"ZRB_INIT_MODULES": "mod1:mod2"}):
        assert config.INIT_MODULES == ["mod1", "mod2"]

    with patch.dict(os.environ, {"ZRB_INIT_MODULES": ""}):
        assert config.INIT_MODULES == []


def test_init_scripts():
    config = Config()
    with patch.dict(os.environ, {"ZRB_INIT_SCRIPTS": "s1.py:s2.py"}):
        assert config.INIT_SCRIPTS == ["s1.py", "s2.py"]


def test_logging_level():
    config = Config()
    with patch.dict(os.environ, {"ZRB_LOGGING_LEVEL": "DEBUG"}):
        assert config.LOGGING_LEVEL == logging.DEBUG

    with patch.dict(os.environ, {"ZRB_LOGGING_LEVEL": "INVALID"}):
        assert config.LOGGING_LEVEL == logging.WARNING


def test_web_paths():
    config = Config()
    with patch.dict(os.environ, {"ZRB_WEB_CSS_PATH": "style.css"}):
        assert config.WEB_CSS_PATH == ["style.css"]

    with patch.dict(os.environ, {"ZRB_WEB_JS_PATH": "script.js"}):
        assert config.WEB_JS_PATH == ["script.js"]


def test_llm_configs_access():
    # Access all LLM properties to ensure coverage
    config = Config()
    assert config.LLM_MODEL is None or isinstance(config.LLM_MODEL, str)
    assert config.LLM_BASE_URL is None or isinstance(config.LLM_BASE_URL, str)
    assert config.LLM_API_KEY is None or isinstance(config.LLM_API_KEY, str)

    assert isinstance(config.LLM_MAX_REQUESTS_PER_MINUTE, int)
    assert isinstance(config.LLM_MAX_TOKENS_PER_MINUTE, int)
    assert isinstance(config.LLM_MAX_TOKENS_PER_REQUEST, int)
    assert isinstance(config.LLM_THROTTLE_SLEEP, float)

    assert isinstance(config.LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD, int)
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
