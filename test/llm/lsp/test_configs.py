from unittest.mock import patch

import pytest

from zrb.llm.lsp.configs import (
    LSP_SERVER_CONFIGS,
    LSPServerConfig,
    detect_available_lsp_servers,
    detect_language_from_file,
    get_lsp_config_for_file,
)


def test_matches_file():
    config = LSPServerConfig(
        name="test_server",
        command=["test_server"],
        language_ids=["testlang"],
        file_extensions=[".test", ".tst"],
    )
    assert config.matches_file("myfile.test") is True
    assert config.matches_file("myfile.tst") is True
    assert config.matches_file("myfile.txt") is False
    assert config.matches_file("no_extension") is False


@patch("shutil.which")
def test_detect_available_lsp_servers(mock_which):
    def which_side_effect(cmd):
        if cmd == "pyright":
            return "/usr/bin/pyright"
        if cmd == "pylsp":
            return "/usr/bin/pylsp"
        return None

    mock_which.side_effect = which_side_effect

    available = detect_available_lsp_servers()

    assert "pyright" in available
    assert available["pyright"] == "/usr/bin/pyright"
    assert "pylsp" in available
    assert available["pylsp"] == "/usr/bin/pylsp"
    assert "jedi" not in available
    assert "gopls" not in available


@patch("zrb.llm.lsp.configs.detect_available_lsp_servers")
def test_get_lsp_config_for_file(mock_detect):
    mock_detect.return_value = {
        "pyright": "/usr/bin/pyright",
        "gopls": "/usr/bin/gopls",
    }

    # Test file matches pyright
    config = get_lsp_config_for_file("script.py")
    assert config is not None
    assert config.name == "pyright"

    # Test file matches gopls
    config = get_lsp_config_for_file("main.go")
    assert config is not None
    assert config.name == "gopls"

    # Test file doesn't match any available server
    config = get_lsp_config_for_file("style.css")
    assert config is None


@patch("zrb.llm.lsp.configs.detect_available_lsp_servers")
def test_get_lsp_config_for_file_with_preferred(mock_detect):
    mock_detect.return_value = {
        "pyright": "/usr/bin/pyright",
        "pylsp": "/usr/bin/pylsp",
    }

    # preferred server 'pylsp' should be chosen over 'pyright'
    config = get_lsp_config_for_file("script.py", preferred_servers=["pylsp"])
    assert config is not None
    assert config.name == "pylsp"

    # preferred server 'not_exist' is not available, should fallback to available ones
    config = get_lsp_config_for_file("script.py", preferred_servers=["not_exist"])
    assert config is not None
    assert config.name == "pyright" or config.name == "pylsp"


def test_detect_language_from_file():
    assert detect_language_from_file("script.py") == "python"
    assert detect_language_from_file("main.go") == "go"
    assert detect_language_from_file("index.ts") == "typescript"
    assert detect_language_from_file("unknown.ext") is None
    assert detect_language_from_file("no_extension") is None
