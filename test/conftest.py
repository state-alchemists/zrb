"""Pytest configuration for hermetic, isolated tests.

The configurable `ZRB_*` namespace is removed before collection, so a test that
asserts a default gets the default whatever the developer's shell carries — an
exported `ZRB_LLM_DICTATION_BARGE_IN_ENABLED=on` failed three default-preset
tests locally, which CI could not reproduce.

The autouse fixtures provide deterministic non-secret defaults and restore
`os.environ` after each test; individual tests may override them temporarily.
"""

import os
import shutil
import tempfile
from collections.abc import MutableMapping
from pathlib import Path

import pytest
import write_guard

# Config reads `<prefix>_<KNOB>`; the prefix itself is `_ZRB_ENV_PREFIX`.
# `DEFAULT_PREFIX` is public because the hermetic-environment test checks it.
_PREFIX_FIELD = "_ZRB_ENV_PREFIX"
DEFAULT_PREFIX = "ZRB"


def _scrub_config_namespace(environ: MutableMapping[str, str]) -> dict[str, str]:
    """Remove the active and default config namespaces, returning removed keys.

    Removing `_ZRB_ENV_PREFIX` also removes both the renamed and default
    namespaces, preventing the default from reviving after the override is gone.
    """
    prefix = environ.get(_PREFIX_FIELD, DEFAULT_PREFIX)
    names = [
        name
        for name in environ
        if name == _PREFIX_FIELD
        or name.startswith(f"{prefix}_")
        or name.startswith(f"{DEFAULT_PREFIX}_")
    ]
    return {name: environ.pop(name) for name in names}


# The developer's real home, kept across the redirect so the write guard can name
# it. It is an internal handoff from the controller to the xdist workers it spawns,
# not a setting: the controller always overwrites it, so a value exported before
# the run cannot switch the redirect off.
_REAL_HOME_VAR = "PYTEST_ZRB_REAL_HOME"
_REDIRECTED_VAR = "PYTEST_ZRB_REDIRECTED"
_TEST_HOME_PREFIX = "zrb-test-home-"
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_test_home: str | None = None


def _redirect_home() -> None:
    """Point `~` at a per-run directory so nothing lands in the real home.

    The controller (any process that is not an xdist worker) creates it before
    xdist spawns the workers, which inherit the environment; only the controller
    removes it, in `pytest_sessionfinish`.
    """
    global _test_home
    if os.environ.get("PYTEST_XDIST_WORKER"):
        return
    if os.environ.get(_REDIRECTED_VAR) == _redirect_marker():
        return  # this process already redirected: do not leak another home
    os.environ[_REAL_HOME_VAR] = os.path.expanduser("~")
    # Resolved, so a symlinked temp root (macOS `/var` -> `/private/var`) does not
    # make `~` differ from the cwd a test changes into.
    home = os.path.realpath(tempfile.mkdtemp(prefix=_TEST_HOME_PREFIX))
    _test_home = home
    os.environ["HOME"] = home
    os.environ["USERPROFILE"] = home  # what `expanduser` reads on Windows
    os.environ[_REDIRECTED_VAR] = _redirect_marker()


def _redirect_marker() -> str:
    """Names this process and the home it was given, so an inherited or stale
    value (another process, another home) never reads as already redirected."""
    return f"{os.getpid()}:{os.environ.get('HOME', '')}"


def _is_real_home(path: str) -> bool:
    real = os.path.realpath(os.environ[_REAL_HOME_VAR])
    return os.path.normcase(os.path.realpath(path)) == os.path.normcase(real)


def pytest_configure() -> None:
    """Remove developer config, redirect home and guard writes, per process."""
    _scrub_config_namespace(os.environ)
    _redirect_home()
    allowed = [tempfile.gettempdir()]
    if not _is_real_home(os.environ["HOME"]):  # never let the real home allow itself
        allowed.append(os.environ["HOME"])
    write_guard.install(
        forbidden_roots=[os.environ[_REAL_HOME_VAR], _REPO_ROOT],
        allowed_roots=allowed,
    )


# Non-secret placeholders; `openai-chat:` selects the model class patched by tests.
_TEST_ENV = {
    "OPENAI_API_KEY": "test-openai-key",
    "BRAVE_API_KEY": "test-brave-key",
    "SERPAPI_KEY": "test-serpapi-key",
    "ZRB_LLM_MODEL": "openai-chat:gpt-4o",
    "ZRB_LLM_SMALL_MODEL": "openai-chat:gpt-4o-mini",
    # Pin the production profile so prompt-composition tests are deterministic.
    "ZRB_LLM_PROFILE": "auto",
    # Disable the built-in journal judge; its dedicated tests re-enable it.
    "ZRB_LLM_JOURNAL_ENABLED": "off",
    # Auto-naming runs a background model call that outlives a short test and
    # leaves a never-awaited coroutine; its dedicated tests re-enable it.
    "ZRB_LLM_AUTO_NAME_ENABLED": "off",
    # Use a per-run speech lock so another zrb process cannot affect the suite.
    "ZRB_LLM_SPEECH_LOCK_FILE": os.path.join(
        tempfile.gettempdir(), f"zrb-test-speech-{os.getpid()}.lock"
    ),
    # Keep the usage log out of the developer's home: every real run appends a
    # line, and a suite run would otherwise leave its own usage behind.
    "ZRB_LLM_USAGE_DIR": os.path.join(
        tempfile.gettempdir(), f"zrb-test-usage-{os.getpid()}"
    ),
    # Same for the stores a run writes to: a delegation saves its transcript and
    # prunes the whole history directory on every save, so a test pointed at the
    # developer's real one scanned ~10,000 files per save (5 s a test) and left
    # its own transcripts behind.
    "ZRB_LLM_HISTORY_DIR": os.path.join(
        tempfile.gettempdir(), f"zrb-test-history-{os.getpid()}"
    ),
    "ZRB_LLM_PREVIOUS_MESSAGE_HISTORY_DIR": os.path.join(
        tempfile.gettempdir(), f"zrb-test-previous-history-{os.getpid()}"
    ),
    "ZRB_LLM_SNAPSHOT_DIR": os.path.join(
        tempfile.gettempdir(), f"zrb-test-snapshots-{os.getpid()}"
    ),
}


def pytest_sessionfinish() -> None:
    """Remove this process's per-run stores, which nothing else would."""
    if _test_home is not None:
        shutil.rmtree(_test_home, ignore_errors=True)
    for key in (
        "ZRB_LLM_USAGE_DIR",
        "ZRB_LLM_HISTORY_DIR",
        "ZRB_LLM_PREVIOUS_MESSAGE_HISTORY_DIR",
        "ZRB_LLM_SNAPSHOT_DIR",
    ):
        shutil.rmtree(_TEST_ENV[key], ignore_errors=True)


@pytest.fixture(autouse=True)
def _no_forbidden_writes():
    """Fail a test whose write the guard refused, even if the test swallowed it."""
    guard = write_guard.install([], [])  # already installed by `pytest_configure`
    seen = len(guard.violations)
    yield
    leaked = guard.violations[seen:]
    assert not leaked, f"test wrote outside temp: {leaked}"


@pytest.fixture
def outside_root():
    """A path outside every root the sandbox keeps writable; it is not created.

    The sandbox keeps both `tempfile.gettempdir()` and, on POSIX, `/tmp`
    writable, and every `tmp_path` lives in one of them (`/tmp/pytest-of-...` on
    Linux, `/var/folders/...` on macOS), so no path under temp can be "outside".
    The developer's real home is outside both on every platform, and the tests
    using this only *evaluate* the path: the write guard still refuses any
    accidental write there.
    """
    real_home = os.environ[_REAL_HOME_VAR]
    outside = os.path.join(real_home, "zrb-test-outside")
    roots = [tempfile.gettempdir()] + (["/tmp"] if os.name == "posix" else [])
    for root in roots:
        if os.path.commonpath(
            [os.path.realpath(outside), os.path.realpath(root)]
        ) == os.path.realpath(root):
            pytest.skip(f"the home {real_home} lies inside the temp root {root}")
    return Path(outside)


@pytest.fixture(autouse=True)
def _hermetic_environment():
    """Apply test defaults and restore ``os.environ`` afterward."""
    saved = dict(os.environ)
    os.environ.update(_TEST_ENV)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)


@pytest.fixture(autouse=True)
def _reset_shell_detection_cache():
    """Clear the process-wide shell-detection cache around each test."""
    from zrb.config.helper import get_windows_posix_shell

    get_windows_posix_shell.cache_clear()
    try:
        yield
    finally:
        get_windows_posix_shell.cache_clear()


@pytest.fixture(autouse=True)
def _reset_unscoped_ambient_state():
    """Restore the three process-wide ambient `ContextVar`s after each test.

    Their setters are intentionally unscoped, so a missed reset can leak session,
    worktree, or interactive-mode state into unrelated tests.
    """
    from zrb.llm.ambient_state import (
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
    """Bind a fresh mutable agent-mode state per test.

    The process-wide default is mutated in place, so an unscoped setter can
    otherwise leave later permission checks in `PLAN` mode.
    """
    from zrb.llm.permission.state import AgentModeState, current_agent_mode

    token = current_agent_mode.set(AgentModeState())
    try:
        yield
    finally:
        current_agent_mode.reset(token)


@pytest.fixture(autouse=True, scope="session")
def _disable_real_filesystem_hooks():
    """Prevent singleton and per-run hook managers from loading user hooks.

    The journal judge is disabled separately by `_TEST_ENV`; tests that need
    hooks construct their own manager with explicit search directories.
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
        hook_manager.search_dirs = []
        hook_manager.reload()
        yield


@pytest.fixture(autouse=True, scope="session")
def _warm_modules_shadowed_by_sys_modules_patches():
    """Warm modules that `sys.modules` patches can evict or shadow.

    Caching `pydantic_ai.toolsets` avoids mocked-parent imports; caching `numpy`
    avoids re-importing its loaded C extension after `patch.dict` restoration.
    Optional dependencies remain guarded.
    """
    for module_name in ("pydantic_ai.toolsets", "numpy"):
        try:
            __import__(module_name)
        except ImportError:
            pass
