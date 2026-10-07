"""Ensure tests ignore developer config before collection.

`ZRB_LLM_DICTATION_BARGE_IN_ENABLED=on` caused default-preset tests to fail
locally while CI could not reproduce them; `pytest_configure` must remove both
configured namespaces without touching unrelated environment keys.
"""

import importlib.util
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "zrb_test_conftest", REPO_ROOT / "test" / "conftest.py"
)
assert _SPEC is not None and _SPEC.loader is not None
suite_config = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = suite_config
_SPEC.loader.exec_module(suite_config)


def test_the_hook_clears_the_namespace_and_leaves_everything_else(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_DICTATION_BARGE_IN_ENABLED", "on")
    monkeypatch.setenv("ZRB_INIT_SCRIPTS", "/tmp/someones-init.py")
    monkeypatch.setenv("ZRBISH_LOOKALIKE", "kept")
    monkeypatch.setenv("OPENAI_API_KEY", "a-real-key")
    suite_config.pytest_configure()
    assert "ZRB_LLM_DICTATION_BARGE_IN_ENABLED" not in os.environ
    assert "ZRB_INIT_SCRIPTS" not in os.environ
    # The separator distinguishes namespace keys from lookalikes.
    assert os.environ["ZRBISH_LOOKALIKE"] == "kept"
    assert os.environ["OPENAI_API_KEY"] == "a-real-key"


def test_a_renamed_namespace_takes_the_default_one_with_it(monkeypatch):
    """Removing the prefix must also remove the revived default namespace."""
    monkeypatch.setenv("_ZRB_ENV_PREFIX", "FOO")
    monkeypatch.setenv("FOO_LLM_PROFILE", "minimal")
    monkeypatch.setenv("ZRB_LLM_PROFILE", "standard")
    suite_config.pytest_configure()
    assert "_ZRB_ENV_PREFIX" not in os.environ
    assert "FOO_LLM_PROFILE" not in os.environ
    assert "ZRB_LLM_PROFILE" not in os.environ


def test_the_namespace_cleared_is_the_one_the_config_reads():
    """Keep the pre-import scrub's copied default prefix tied to `CFG`."""
    from zrb.config.config import CFG

    assert suite_config.DEFAULT_PREFIX == CFG.ENV_PREFIX
