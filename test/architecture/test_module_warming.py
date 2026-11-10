"""Name the test that breaks a warmed module, instead of reporting its shadow.

One xdist worker met `pydantic_ai.providers.openai` replaced and six unrelated
files went red with `ImportError: cannot import name 'OpenAIProvider'`: the
report named pydantic-ai everywhere and the test that broke it nowhere. The
suite warms those modules at session start and fails the test that replaces one.
"""

import importlib.util
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "zrb_test_conftest_warming", REPO_ROOT / "test" / "conftest.py"
)
assert _SPEC is not None and _SPEC.loader is not None
suite_config = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = suite_config
_SPEC.loader.exec_module(suite_config)


def test_the_provider_modules_reach_a_test_complete():
    """The guard only holds while the session warm-up keeps the modules whole."""
    for name in ("openai", "pydantic_ai.providers.openai"):
        assert name in sys.modules, f"{name} was never imported"
    assert hasattr(sys.modules["pydantic_ai.providers.openai"], "OpenAIProvider")


def test_a_module_that_is_still_the_one_warmed_is_not_reported():
    module = sys.modules["openai"]
    assert suite_config.replaced_warmed_modules({"openai": module}) == []


def test_a_replaced_module_is_reported_by_name(monkeypatch):
    warmed = types.ModuleType("openai")
    intruder = types.ModuleType("openai")
    monkeypatch.setitem(sys.modules, "openai", intruder)
    assert suite_config.replaced_warmed_modules({"openai": warmed}) == ["openai"]


def test_an_evicted_module_is_reported_too(monkeypatch):
    """`patch.dict` restoring a *deleted* key leaves nothing behind either."""
    warmed = types.ModuleType("numpy")
    monkeypatch.delitem(sys.modules, "numpy", raising=False)
    assert suite_config.replaced_warmed_modules({"numpy": warmed}) == ["numpy"]
