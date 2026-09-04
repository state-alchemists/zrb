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
def _reset_unscoped_ambient_state():
    """Restore every unscoped ambient ``ContextVar`` after each test.

    Three setters in ``zrb.llm.tool.ambient_state`` do a bare, unscoped
    ``ContextVar.set()`` — by design, each is meant to be called once for a
    process's lifetime (see their own docstrings), so none has a
    ``scoped()``/token-based reset counterpart
    (``zrb.util.contextvar_scope``): ``set_current_session``,
    ``set_active_worktree`` and ``set_interactive_mode``.

    A test that calls one directly and forgets to reset (three did, in
    ``test/llm/tool/test_plan.py``) leaks the value into every later test
    sharing this worker process — not just tests that touch that ContextVar
    themselves, but any test whose code path reads it and assumes the
    default, such as ``DelegateToAgent``'s live session registry lookup
    (``get_session_ownership_key()``), ``Shell``'s worktree resolution, or
    ``ask_user_question``'s non-interactive short-circuit. That leak caused
    exactly this: rare, worker-assignment-dependent failures in unrelated
    tests, previously misread as async-cancellation timing flakiness in
    ``test/llm/tool/test_delegate_tool.py``.

    All three are restored here rather than only the session one: the other
    two are currently safe by coincidence — every caller happens to restore
    the literal that equals the var's default (``""`` / ``True``) — which is
    not an invariant anything enforces. This fixture makes all three
    self-healing regardless of whether a future test remembers to clean up.
    """
    from zrb.llm.tool.ambient_state import (
        get_active_worktree,
        get_current_context_session,
        get_interactive_mode,
        set_active_worktree,
        set_current_session,
        set_interactive_mode,
    )

    saved_session = get_current_context_session()
    saved_worktree = get_active_worktree()
    saved_interactive = get_interactive_mode()
    try:
        yield
    finally:
        set_current_session(saved_session)
        set_active_worktree(saved_worktree)
        set_interactive_mode(saved_interactive)


@pytest.fixture(autouse=True)
def _isolate_agent_mode():
    """Bind a fresh ``AgentModeState`` per test so nothing mutates the shared
    process-wide default.

    ``current_agent_mode``'s default is a single **mutable** instance created
    at import time, and ``set_current_agent_mode`` mutates it in place — that
    is deliberate, it is how an in-run ``ExitPlanMode`` reaches the per-tool-call
    tasks pydantic-ai spawns (see ``permission/state.py``). Production code
    binds a run-local instance first (``enter_agent_mode_scope``); a test that
    calls the setter without one writes straight to the shared default.

    Tests that do this restore by assigning ``BUILD`` back in a ``finally``,
    which is correct only while ``BUILD`` stays the default and only while the
    body reaches the ``finally``. A raise on the restore line, or a new test
    that forgets one, leaves the whole worker in ``PLAN`` — flipping
    ``get_effective_policy()`` to ``PLAN_MODE_POLICY`` for every later test
    that reads a permission gate. Binding a fresh instance here makes those
    writes land on a per-test object that is discarded, so the default can
    never be reached at all.
    """
    from zrb.llm.permission.state import AgentModeState, current_agent_mode

    token = current_agent_mode.set(AgentModeState())
    try:
        yield
    finally:
        current_agent_mode.reset(token)


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
def _warm_modules_shadowed_by_sys_modules_patches():
    """Import for real, once per worker process, every module that a
    ``patch.dict("sys.modules", ...)`` block elsewhere in the suite either
    shadows or causes to be imported lazily underneath it.

    Two distinct failures, one cause — a mocked ``sys.modules`` entry standing
    where a real import is about to happen:

    ``pydantic_ai.toolsets``: the agent-hook tests (``test/llm/hook/``,
    ``test/llm/agent/test_hook_agent.py``) shadow the top-level
    ``pydantic_ai`` package with a ``MagicMock``. Once
    ``sys.modules["pydantic_ai.toolsets"]`` is cached for real, `from
    pydantic_ai.toolsets import X` resolves straight from that cache — Python
    only needs the (mocked) parent package when the submodule isn't already
    cached. Without this, whichever test runs first in a fresh process fails
    with "No module named 'pydantic_ai.toolsets'; 'pydantic_ai' is not a
    package", since the code path under test lazily imports it for the first
    time while the mock is active.

    ``numpy``: ``unittest.mock.patch.dict`` restores by ``clear()`` +
    ``update(snapshot)``, so **any module imported for the first time inside
    the block is deleted from ``sys.modules`` on exit**. ``VoiceEngine.record``
    lazily does ``import numpy`` inside ``test/llm/voice/test_engine.py``'s
    ``patch.dict("sys.modules", {"sounddevice": ...})``, which evicts numpy's
    entries while its C extension stays loaded in the process — so the next
    ``import numpy`` raises "ImportError: cannot load module more than once
    per process" (a hard error since CPython 3.12). Warming it here puts numpy
    in the snapshot, so the restore keeps it.

    Both are order-dependent: serial runs masked them because some earlier
    test always imported the module for real first, and pytest-xdist's
    per-worker processes with ``--dist load`` (which splits a file's tests
    across workers) made them visible. Guarded imports — an optional extra
    that isn't installed can't be evicted, because nothing imports it for
    real either.
    """
    for module_name in ("pydantic_ai.toolsets", "numpy"):
        try:
            __import__(module_name)
        except ImportError:
            pass
