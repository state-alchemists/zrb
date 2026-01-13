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


def test_get_internal_default_prompt():
    config = Config()
    # MagicMock file reading
    with patch("builtins.open", mock_open(read_data="prompt content")):
        prompt = config._get_internal_default_prompt("test_prompt")
        assert prompt == "prompt content"
        # Test caching (should not open file again)
        prompt = config._get_internal_default_prompt("test_prompt")
        assert prompt == "prompt content"


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

    assert config.LLM_MODEL_SMALL is None or isinstance(config.LLM_MODEL_SMALL, str)
    assert config.LLM_BASE_URL_SMALL is None or isinstance(
        config.LLM_BASE_URL_SMALL, str
    )
    assert config.LLM_API_KEY_SMALL is None or isinstance(config.LLM_API_KEY_SMALL, str)

    assert config.LLM_SYSTEM_PROMPT is None or isinstance(config.LLM_SYSTEM_PROMPT, str)
    assert config.LLM_INTERACTIVE_SYSTEM_PROMPT is None or isinstance(
        config.LLM_INTERACTIVE_SYSTEM_PROMPT, str
    )
    assert config.LLM_PERSONA is None or isinstance(config.LLM_PERSONA, str)

    assert isinstance(config.LLM_WORKFLOWS, list)
    assert isinstance(config.LLM_BUILTIN_WORKFLOW_PATHS, list)

    assert config.LLM_SPECIAL_INSTRUCTION_PROMPT is None or isinstance(
        config.LLM_SPECIAL_INSTRUCTION_PROMPT, str
    )
    assert config.LLM_SUMMARIZATION_PROMPT is None or isinstance(
        config.LLM_SUMMARIZATION_PROMPT, str
    )

    assert isinstance(config.LLM_SHOW_TOOL_CALL_PREPARATION, bool)
    assert isinstance(config.LLM_SHOW_TOOL_CALL_RESULT, bool)

    assert isinstance(config.LLM_MAX_REQUESTS_PER_MINUTE, int)
    assert isinstance(config.LLM_MAX_TOKENS_PER_MINUTE, int)
    assert isinstance(config.LLM_MAX_TOKENS_PER_REQUEST, int)
    assert isinstance(config.LLM_MAX_TOKENS_PER_TOOL_CALL_RESULT, int)
    assert isinstance(config.LLM_THROTTLE_SLEEP, float)

    assert isinstance(config.LLM_YOLO_MODE, (bool, list))
    assert isinstance(config.LLM_SUMMARIZE_HISTORY, bool)

    assert isinstance(config.LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD, int)
    assert isinstance(config.LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD, int)
    assert isinstance(config.LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD, int)
    assert isinstance(config.LLM_FILE_ANALYSIS_TOKEN_THRESHOLD, int)

    # Test prompt loading with mock to avoid file reading
    with patch.object(config, "_get_internal_default_prompt", return_value="prompt"):
        assert config.LLM_FILE_EXTRACTOR_SYSTEM_PROMPT == "prompt"
        assert config.LLM_REPO_EXTRACTOR_SYSTEM_PROMPT == "prompt"
        assert config.LLM_REPO_SUMMARIZER_SYSTEM_PROMPT == "prompt"

    assert isinstance(config.LLM_HISTORY_DIR, str)
    assert isinstance(config.LLM_ALLOW_ACCESS_LOCAL_FILE, bool)
    assert isinstance(config.LLM_ALLOW_ANALYZE_FILE, bool)
    assert isinstance(config.LLM_ALLOW_ANALYZE_REPO, bool)
    assert isinstance(config.LLM_ALLOW_ACCESS_SHELL, bool)
    assert isinstance(config.LLM_ALLOW_OPEN_WEB_PAGE, bool)
    assert isinstance(config.LLM_ALLOW_SEARCH_INTERNET, bool)
    assert isinstance(config.LLM_ALLOW_GET_CURRENT_LOCATION, bool)
    assert isinstance(config.LLM_ALLOW_GET_CURRENT_WEATHER, bool)

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
    assert isinstance(config.LLM_CONTEXT_FILE, str)
    assert isinstance(config.USE_TIKTOKEN, bool)
    assert isinstance(config.TIKTOKEN_ENCODING_NAME, str)


def test_llm_yolo_mode_parsing():
    config = Config()
    with patch.dict(os.environ, {"ZRB_LLM_YOLO_MODE": "tool1, tool2"}):
        assert config.LLM_YOLO_MODE == ["tool1", "tool2"]

    with patch.dict(os.environ, {"ZRB_LLM_YOLO_MODE": "true"}):
        assert config.LLM_YOLO_MODE is True
