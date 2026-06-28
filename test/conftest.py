"""Shared pytest configuration that makes the suite hermetic.

Tests must not depend on the developer's ambient shell (provider API keys,
model selection) or leak environment mutations into one another. Before this
fixture existed the suite only passed when the developer happened to have
`OPENAI_API_KEY` / `BRAVE_API_KEY` / `SERPAPI_KEY` / `ZRB_LLM_MODEL` exported;
in a clean environment (e.g. CI) ~30 tests failed at agent/client construction
or in the search tools.

The autouse fixture below:
  1. Provides deterministic, non-secret defaults so eager client construction
     and "is a key/model configured?" guards succeed. The actual model and
     network calls are mocked inside the tests — these values only satisfy
     construction-time checks.
  2. Snapshots and restores ``os.environ`` around every test, so a test that
     writes env via ``CFG``'s setters cannot leak state into later tests.

Individual tests may still override any of these with ``patch.dict`` /
``monkeypatch`` — those layer on top and are torn down before the snapshot is
restored.
"""

import os

import pytest

# Non-secret placeholders. The "openai-chat:" prefix is explicit on purpose:
# a bare "gpt-4o" makes pydantic-ai emit a "no provider prefix" deprecation and
# then a second warning about "openai:" defaulting to the Responses API in v2.0.
# "openai-chat:" pins the Chat Completions OpenAIModel (which the tests that
# patch pydantic_ai.models.openai.OpenAIModel expect) and silences both. The
# dummy OPENAI_API_KEY is enough to construct it (real calls are mocked).
_TEST_ENV = {
    "OPENAI_API_KEY": "test-openai-key",
    "BRAVE_API_KEY": "test-brave-key",
    "SERPAPI_KEY": "test-serpapi-key",
    "ZRB_LLM_MODEL": "openai-chat:gpt-4o",
    "ZRB_LLM_SMALL_MODEL": "openai-chat:gpt-4o-mini",
    # Pin the prompt profile to its production default so prompt-composition
    # tests are deterministic regardless of the developer's shell. A developer
    # with ZRB_LLM_PROFILE=explicit exported would otherwise see the explicit
    # phrasing variants leak into tests that assert on the default (terse)
    # composition. Tests exercising explicit override this with patch.dict
    # (which layers on top of this default).
    "ZRB_LLM_PROFILE": "auto",
}


@pytest.fixture(autouse=True)
def _hermetic_environment():
    """Apply deterministic env defaults and restore ``os.environ`` afterward."""
    saved = dict(os.environ)
    os.environ.update(_TEST_ENV)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)


@pytest.fixture(autouse=True, scope="session")
def _disable_real_filesystem_hooks():
    """Keep the process-wide ``hook_manager`` singleton from discovering the
    developer's real ``~/.claude`` hooks (e.g. peon-ping) during the suite.

    The singleton is imported under one shared object by the runner, llm_task,
    ui, skill manager and the ask tool. Once command hooks began loading from
    ``settings.json``, any test that emits a hook event — ``ask_user_question``'s
    ``Notification``, the runner's ``Stop`` — spawned the user's real async hook
    subprocesses (peon-ping's ``peon.sh``). With no audio device (CI/WSL) those
    linger and hang asyncio's subprocess-transport teardown when the per-test
    event loop closes, making the suite crawl and eventually time out.

    Pinning the singleton's search dirs to ``[]`` and reloading keeps it inert;
    tests that need hook behaviour build their own ``HookManager(search_dirs=[])``.
    """
    from zrb.llm.hook.manager import hook_manager

    hook_manager._search_dirs = []  # backing field of the search_dirs ctor arg
    hook_manager.reload()  # reset registrations + reload from [] → no fs hooks
    yield
