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
    # with ZRB_LLM_PROFILE=minimal exported would otherwise see that preset's
    # phrasing variants leak into tests that assert on the default (full)
    # composition. Tests exercising another preset override this with
    # patch.dict / monkeypatch (which layer on top of this default).
    "ZRB_LLM_PROFILE": "auto",
    # Off by default so the built-in journal-compliance judge (a Stop hook
    # seeded into every HookManager, not filesystem-scanned like the peon-ping
    # neutering below) stays a no-op: without this, any test whose Stop event
    # happens to carry wrote_files=True — not just the ones dedicated to
    # testing it — silently spawns a real background LLM call that outlives
    # the test, leaking an unawaited-coroutine warning into whichever test
    # runs next. Tests exercising the judge re-enable it explicitly
    # (test/llm/hook/test_journal_compliance.py).
    "ZRB_LLM_JOURNAL_ENABLED": "off",
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


@pytest.fixture(autouse=True)
def _reset_current_tool_session():
    """Restore the ambient tool session (``_current_session`` in
    ``zrb.llm.tool.ambient_state``) after every test.

    ``set_current_session`` does a bare, unscoped ``ContextVar.set()`` — by
    design, it is meant to be called once for a process's lifetime (see its
    own docstring), so it has no ``scoped()``/token-based reset counterpart
    (``zrb.util.contextvar_scope``). A test that calls it directly and
    forgets to reset (three did, in ``test/llm/tool/test_plan.py``) leaks the
    value into every later test sharing this worker process — not just tests
    that touch this ContextVar themselves, but any test whose code path reads
    ``get_current_tool_session()``/``get_session_ownership_key()`` and
    assumes the default ("default"), such as ``DelegateToAgent``'s live
    session registry lookup. That leak caused exactly this: rare,
    worker-assignment-dependent failures in unrelated tests, previously
    misread as async-cancellation timing flakiness in
    ``test/llm/tool/test_delegate_tool.py``. This fixture makes the leak
    self-healing regardless of whether a future test remembers to clean up.
    """
    from zrb.llm.tool.ambient_state import get_current_context_session, set_current_session

    saved = get_current_context_session()
    try:
        yield
    finally:
        set_current_session(saved)


@pytest.fixture(autouse=True, scope="session")
def _disable_real_filesystem_hooks():
    """Keep *every* ``HookManager`` from discovering the developer's real
    ``~/.claude`` hooks (e.g. peon-ping) during the suite.

    Once command hooks began loading from ``settings.json``, any test that emits
    a hook event — ``ask_user_question``'s ``Notification``, the runner's
    ``Stop`` — spawned the user's real async hook subprocesses (peon-ping's
    ``peon.sh``). With no audio device (CI/WSL) those linger and hang asyncio's
    subprocess-transport teardown when the per-test event loop closes, making
    the suite crawl and eventually time out.

    Two things need neutering, not one:

    - the process-wide singleton, imported under one shared object by the
      runner, llm_task, ui, skill manager and the ask tool; and
    - the **per-execution** managers, because ``_create_llm_task_core`` and
      ``LLMTaskBuilding`` build a bare ``HookManager()`` per chat run and each
      instance resolves its own search dirs. Pinning only the singleton left
      those loading the real hooks, so a non-interactive chat test still
      spawned ``peon.sh``.

    The construction sites are patched rather than ``get_search_directories``
    itself, which several tests in ``test/llm/hook/`` legitimately exercise for
    real. Tests that want hook behaviour keep building their own
    ``HookManager(search_dirs=[...])`` directly.

    The built-in journal-compliance judge (also seeded into every
    ``HookManager`` — not filesystem-scanned, so ``search_dirs=[]`` alone
    doesn't stop it) is handled separately: ``_TEST_ENV`` below defaults
    ``ZRB_LLM_JOURNAL_ENABLED`` off, so its factory registers nothing unless a
    test explicitly re-enables it — see ``test/llm/hook/
    test_journal_compliance.py``.
    """
    from unittest.mock import patch

    import zrb.llm.task.building as llm_task_building
    import zrb.llm.task.chat.execution as chat_execution
    from zrb.llm.hook.manager import HookManager, hook_manager

    class _InertHookManager(HookManager):
        """A HookManager that never discovers filesystem hooks."""

        def __init__(self, *args, **kwargs):
            kwargs.setdefault("search_dirs", [])
            super().__init__(*args, **kwargs)

    with (
        patch.object(chat_execution, "HookManager", _InertHookManager),
        patch.object(llm_task_building, "HookManager", _InertHookManager),
    ):
        hook_manager.search_dirs = []  # discover nothing from the filesystem
        hook_manager.reload()  # reset registrations + reload from [] → no fs hooks
        yield


@pytest.fixture(autouse=True, scope="session")
def _warm_pydantic_ai_toolsets_import():
    """Force a real ``pydantic_ai.toolsets`` import once per worker process,
    before any test's ``patch.dict("sys.modules", {"pydantic_ai":
    MagicMock(...)})`` (agent-hook tests in ``test/llm/hook/`` and
    ``test/llm/agent/test_hook_agent.py``) can shadow the top-level package.

    Once ``sys.modules["pydantic_ai.toolsets"]`` is cached for real, `from
    pydantic_ai.toolsets import X` resolves straight from that cache — Python
    only needs the (mocked) parent package when the submodule isn't already
    cached. Without this, whichever test happens to run first in a fresh
    process fails with "No module named 'pydantic_ai.toolsets'; 'pydantic_ai'
    is not a package", since the agent-hook code path under test lazily
    imports it for the first time while the mock is active. Order-dependent:
    serial runs masked it because some earlier test always imported it for
    real first; pytest-xdist's per-worker processes made it visible.
    """
    import pydantic_ai.toolsets  # noqa: F401
