"""The suite must not read the developer's config namespace.

`Config` reads its knobs from `<prefix>_<KNOB>` — `ZRB_*`, renamed by
`_ZRB_ENV_PREFIX` — so a variable exported for one `zrb` run, or sourced from a
`.env`, would otherwise decide what the suite sees. The failure is concrete:
`test/config/test_config_voice_preset.py` asserts the preset a *default* shell
implies, and three of its tests fail on a machine with
`ZRB_LLM_DICTATION_BARGE_IN_ENABLED=on` exported. Nothing raises and no gate
complains there — the failures read as broken tests, and CI, which exports
nothing, can never reproduce them.

`test/conftest.py::pytest_configure` closes it by removing the namespace before
collection. That file is loaded here by path rather than imported: pytest imports
conftest modules under its own rootdir-relative name, and a test reaching for
`import conftest` would be depending on that name.

Each case drives that hook and reads `os.environ` back, rather than calling the
scrub directly, so nothing outside `conftest.py` is named here.
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
    # The separator is what delimits the namespace, so a name that merely begins
    # with the prefix is not config and keeps whatever it holds — as does a key
    # that was never in the namespace at all.
    assert os.environ["ZRBISH_LOOKALIKE"] == "kept"
    assert os.environ["OPENAI_API_KEY"] == "a-real-key"


def test_a_renamed_namespace_takes_the_default_one_with_it(monkeypatch):
    """Both go, because dropping the prefix field revives the default namespace.

    A developer who renamed theirs left every `ZRB_*` key inert, so clearing only
    the renamed one would make those keys live again the moment the field
    shadowing them was removed.
    """
    monkeypatch.setenv("_ZRB_ENV_PREFIX", "FOO")
    monkeypatch.setenv("FOO_LLM_PROFILE", "minimal")
    monkeypatch.setenv("ZRB_LLM_PROFILE", "standard")
    suite_config.pytest_configure()
    assert "_ZRB_ENV_PREFIX" not in os.environ
    assert "FOO_LLM_PROFILE" not in os.environ
    assert "ZRB_LLM_PROFILE" not in os.environ


def test_the_namespace_cleared_is_the_one_the_config_reads():
    """The default prefix is a copy of zrb's; this is what keeps the copy honest.

    The scrub runs before collection, so it cannot import `zrb.config` to ask for
    the prefix — that would load the config module before the suite is ready for
    it. Binding the copy to the original here is the cheaper half of the same
    guarantee: change zrb's default and this fails, rather than leaving the suite
    quietly clearing a namespace nothing reads.
    """
    from zrb.config.config import CFG

    assert suite_config.DEFAULT_PREFIX == CFG.ENV_PREFIX
