"""Tests for the `HookRegistry` split-out (ADR-0090).

A registry is the canonical hook collection: it stores event-keyed and global
hooks plus their config bookkeeping, and answers queries. It does not scan the
filesystem or run hooks — that is `HookManager`'s job. Tests drive the registry
through a manager that shares it (the public boundary), mirroring how
`zrb_init.py` and the module singleton wire up.
"""

import pytest

from zrb.llm.hook.interface import HookCallable, HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.registry import HookRegistry, hook_registry
from zrb.llm.hook.schema import CommandHookConfig, HookConfig
from zrb.llm.hook.types import HookEvent, HookType


@pytest.fixture
def registry():
    return HookRegistry()


@pytest.fixture
def manager(registry):
    return HookManager(registry=registry, search_dirs=[])


def _hook(name="h"):
    async def hook(ctx) -> HookResult:
        return HookResult(success=True, output=name)

    hook.__name__ = name
    return hook


def _config(event: HookEvent, priority: int = 0) -> HookConfig:
    return HookConfig(
        name="cfg",
        events=[event],
        type=HookType.COMMAND,
        config=CommandHookConfig(command=""),
        priority=priority,
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_registry_constructed_empty(registry):
    assert registry.get_hooks(HookEvent.NOTIFICATION) == []
    assert registry.get_global_hooks() == []


def test_manager_defaults_to_fresh_isolated_registry():
    manager = HookManager()
    assert manager.registry is not hook_registry
    another = HookManager()
    assert another.registry is not manager.registry


def test_singleton_is_hook_registry():
    assert isinstance(hook_registry, HookRegistry)


# ---------------------------------------------------------------------------
# register / get_hooks / get_global_hooks
# ---------------------------------------------------------------------------


def test_register_event_hook(manager, registry):
    hook = _hook()
    manager.register(hook, events=[HookEvent.NOTIFICATION])
    assert registry.get_hooks(HookEvent.NOTIFICATION) == [hook]
    assert registry.get_global_hooks() == []


def test_register_global_hook(manager, registry):
    hook = _hook()
    manager.register(hook)
    assert registry.get_global_hooks() == [hook]
    assert registry.get_hooks(HookEvent.NOTIFICATION) == []


def test_register_global_with_empty_events(manager, registry):
    hook = _hook()
    manager.register(hook, events=[])
    assert registry.get_global_hooks() == [hook]


def test_register_hook_multiple_events(manager, registry):
    hook = _hook()
    manager.register(hook, events=[HookEvent.STOP, HookEvent.SESSION_END])
    assert registry.get_hooks(HookEvent.STOP) == [hook]
    assert registry.get_hooks(HookEvent.SESSION_END) == [hook]


def test_hook_with_config_recorded(manager, registry):
    hook = _hook()
    config = _config(HookEvent.NOTIFICATION, priority=5)
    manager.register(hook, events=[HookEvent.NOTIFICATION], config=config)
    assert registry.get_hook_config(hook) is config


def test_record_config_for_debugging(registry):
    config = _config(HookEvent.NOTIFICATION, priority=5)
    registry.record_config("cfg", config)
    assert registry.get_configs()["cfg"] is config


# ---------------------------------------------------------------------------
# remove_hook / remove_event_hooks
# ---------------------------------------------------------------------------


def test_remove_hook_drops_everywhere(manager, registry):
    hook = _hook()
    manager.register(hook, events=[HookEvent.STOP, HookEvent.SESSION_END])
    manager.remove_hook(hook)
    assert registry.get_hooks(HookEvent.STOP) == []
    assert registry.get_hooks(HookEvent.SESSION_END) == []
    assert registry.get_hook_config(hook) is None


def test_remove_global_hook(manager, registry):
    hook = _hook()
    manager.register(hook)
    manager.remove_hook(hook)
    assert registry.get_global_hooks() == []


def test_remove_event_hooks_keeps_global(manager, registry):
    event_hook = _hook("event")
    global_hook = _hook("global")
    manager.register(event_hook, events=[HookEvent.NOTIFICATION])
    manager.register(global_hook)
    manager.remove_event_hooks(HookEvent.NOTIFICATION)
    assert registry.get_hooks(HookEvent.NOTIFICATION) == []
    assert registry.get_global_hooks() == [global_hook]


def test_remove_hook_unknown_is_noop(manager):
    manager.remove_hook(_hook())


# ---------------------------------------------------------------------------
# set_hooks (per-event replacement, ADR-0090 Part 4)
# ---------------------------------------------------------------------------


def test_set_hooks_replaces_event(manager, registry):
    old = _hook("old")
    new_hook = _hook("new")
    manager.register(old, events=[HookEvent.NOTIFICATION])
    manager.set_hooks(HookEvent.NOTIFICATION, [new_hook])
    assert registry.get_hooks(HookEvent.NOTIFICATION) == [new_hook]
    assert old not in registry.get_hooks(HookEvent.NOTIFICATION)


def test_set_hooks_with_configs(manager, registry):
    new_hook = _hook("new")
    config = _config(HookEvent.NOTIFICATION, priority=9)
    manager.set_hooks(HookEvent.NOTIFICATION, [new_hook], configs={new_hook: config})
    assert registry.get_hook_config(new_hook) is config


def test_set_hooks_prunes_stale_configs(manager, registry):
    old = _hook("old")
    new_hook = _hook("new")
    config = _config(HookEvent.NOTIFICATION)
    manager.register(old, events=[HookEvent.NOTIFICATION], config=config)
    manager.set_hooks(HookEvent.NOTIFICATION, [new_hook])
    assert registry.get_hook_config(old) is None


def test_remove_event_hooks_prunes_stale_configs(manager, registry):
    hook = _hook("h")
    config = _config(HookEvent.NOTIFICATION)
    manager.register(hook, events=[HookEvent.NOTIFICATION], config=config)
    manager.remove_event_hooks(HookEvent.NOTIFICATION)
    assert registry.get_hook_config(hook) is None


# ---------------------------------------------------------------------------
# reload keeps a fresh registry view; manager reload clears then rescans
# ---------------------------------------------------------------------------


def test_reload_clears_registered_hooks(manager, registry):
    hook = _hook()
    manager.register(hook, events=[HookEvent.NOTIFICATION])
    manager.reload()
    # reload rescans nothing (search_dirs=[]) so the registry is empty
    assert registry.get_hooks(HookEvent.NOTIFICATION) == []


# ---------------------------------------------------------------------------
# LLM_HOOKS twin
# ---------------------------------------------------------------------------


def test_llm_hooks_allowlist_filters_event_and_global(registry, monkeypatch):
    event = HookEvent.SESSION_START
    alpha, beta = _hook("alpha"), _hook("beta")
    registry.register(alpha, events=[event])
    registry.register(beta, events=[event])
    gamma = _hook("gamma")
    registry.register(gamma)
    monkeypatch.setenv("ZRB_LLM_HOOKS", "beta,gamma")
    assert registry.get_hooks(event) == [beta]
    assert registry.get_global_hooks() == [gamma]
    monkeypatch.setenv("ZRB_LLM_HOOKS", "")
    assert set(registry.get_hooks(event)) == {alpha, beta}
    assert registry.get_global_hooks() == [gamma]


def test_llm_hooks_allowlist_uses_config_name(registry, monkeypatch):
    event = HookEvent.PRE_COMPACT

    async def hook(ctx) -> HookResult:
        return HookResult(success=True, output="x")

    config = _config(event)
    registry.register(hook, events=[event], config=config)
    monkeypatch.setenv("ZRB_LLM_HOOKS", "cfg")
    assert registry.get_hooks(event) == [hook]
    monkeypatch.setenv("ZRB_LLM_HOOKS", "not-cfg")
    assert registry.get_hooks(event) == []
