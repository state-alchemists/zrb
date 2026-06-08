"""Tests for ambient permission state and the execution-gate enforcement."""

import pytest

from zrb.llm.permission import (
    AgentMode,
    Capability,
    PermissionPolicy,
    Rule,
    current_agent_mode,
    current_permission_policy,
    get_effective_policy,
    tag,
)
from zrb.llm.permission.state import AgentModeState

# --- get_effective_policy ------------------------------------------------


def test_default_effective_policy_is_none():
    assert get_effective_policy() is None


def test_public_setters_and_getters_round_trip():
    from zrb.llm.permission import (
        AgentMode,
        get_current_agent_mode,
        get_current_permission_policy,
        set_current_agent_mode,
        set_current_permission_policy,
    )

    policy = PermissionPolicy((Rule("*", "deny"),))
    set_current_permission_policy(policy)
    set_current_agent_mode(AgentMode.PLAN)
    try:
        assert get_current_permission_policy() is policy
        assert get_current_agent_mode() == AgentMode.PLAN
    finally:
        set_current_permission_policy(None)
        set_current_agent_mode(AgentMode.BUILD)


def test_explicit_policy_is_returned():
    policy = PermissionPolicy((Rule("*", "allow"),))
    token = current_permission_policy.set(policy)
    try:
        assert get_effective_policy() is policy
    finally:
        current_permission_policy.reset(token)


@pytest.mark.asyncio
async def test_agent_mode_is_isolated_per_run():
    """Concurrent runs must not share agent mode (regression for H11).

    Each run binds its own ``AgentModeState`` via ``enter_agent_mode_scope`` and
    mutates only that instance, so one conversation switching to BUILD cannot
    flip another that is in PLAN.
    """
    import asyncio

    from zrb.llm.permission.state import (
        enter_agent_mode_scope,
        exit_agent_mode_scope,
        get_current_agent_mode,
        set_current_agent_mode,
    )

    started = asyncio.Event()

    async def run_in_plan():
        token, parent = enter_agent_mode_scope()
        try:
            set_current_agent_mode(AgentMode.PLAN)
            started.set()
            await asyncio.sleep(0.05)
            # Must stay PLAN even though the sibling run flips to BUILD.
            assert get_current_agent_mode() == AgentMode.PLAN
        finally:
            exit_agent_mode_scope(token, parent)

    async def run_in_build():
        await started.wait()
        token, parent = enter_agent_mode_scope()
        try:
            set_current_agent_mode(AgentMode.BUILD)
            assert get_current_agent_mode() == AgentMode.BUILD
        finally:
            exit_agent_mode_scope(token, parent)

    try:
        await asyncio.gather(run_in_plan(), run_in_build())
    finally:
        # The write-back leaves the shared default mutated; reset for other tests.
        set_current_agent_mode(AgentMode.BUILD)


def test_in_run_mode_switch_propagates_to_caller():
    """An in-run ExitPlanMode persists for the caller after the scope closes."""
    from zrb.llm.permission.state import (
        enter_agent_mode_scope,
        exit_agent_mode_scope,
        get_current_agent_mode,
        set_current_agent_mode,
    )

    set_current_agent_mode(AgentMode.PLAN)
    try:
        token, parent = enter_agent_mode_scope()
        assert get_current_agent_mode() == AgentMode.PLAN  # inherited
        set_current_agent_mode(AgentMode.BUILD)  # e.g. ExitPlanMode mid-run
        exit_agent_mode_scope(token, parent)
        # Caller observes the final in-run mode (sticky across turns).
        assert get_current_agent_mode() == AgentMode.BUILD
    finally:
        set_current_agent_mode(AgentMode.BUILD)


def test_plan_mode_overrides_explicit_policy():
    from zrb.llm.permission import PLAN_MODE_POLICY

    policy = PermissionPolicy((Rule("*", "allow"),))
    t1 = current_permission_policy.set(policy)
    t2 = current_agent_mode.set(AgentModeState(mode=AgentMode.PLAN))
    try:
        assert get_effective_policy() is PLAN_MODE_POLICY
    finally:
        current_agent_mode.reset(t2)
        current_permission_policy.reset(t1)


# --- execution gate (create_safe_wrapper) --------------------------------


@pytest.mark.asyncio
async def test_gate_blocks_denied_tool():
    from zrb.llm.agent.common import create_safe_wrapper

    calls = []

    def mutate(path: str = ""):
        calls.append(path)
        return "did it"

    tag(mutate, Capability.EDIT)
    wrapped = create_safe_wrapper(mutate)

    policy = PermissionPolicy((Rule(Capability.EDIT.value, "deny"),))
    token = current_permission_policy.set(policy)
    try:
        result = await wrapped(path="x.txt")
    finally:
        current_permission_policy.reset(token)

    assert result.metadata.get("blocked") is True
    assert calls == []  # never executed


@pytest.mark.asyncio
async def test_gate_allows_non_denied_tool():
    from zrb.llm.agent.common import create_safe_wrapper

    def read(path: str = ""):
        return "content"

    tag(read, Capability.READ)
    wrapped = create_safe_wrapper(read)

    policy = PermissionPolicy((Rule(Capability.EDIT.value, "deny"), Rule("*", "allow")))
    token = current_permission_policy.set(policy)
    try:
        result = await wrapped(path="x.txt")
    finally:
        current_permission_policy.reset(token)

    assert result.content == "content"
    assert "blocked" not in result.metadata


@pytest.mark.asyncio
async def test_gate_inert_without_policy():
    """Default-off: no policy → tool runs exactly as before."""
    from zrb.llm.agent.common import create_safe_wrapper

    def mutate():
        return "did it"

    tag(mutate, Capability.EDIT)
    wrapped = create_safe_wrapper(mutate)

    result = await wrapped()
    assert result.content == "did it"
    assert "blocked" not in result.metadata


# --- inheritance checker consulting the policy ---------------------------


def test_inheritance_checker_uses_policy():
    from zrb.llm.agent.subagent.yolo import make_yolo_inheritance_checker

    policy = PermissionPolicy((Rule("Read", "allow"), Rule("*", "ask")))
    token = current_permission_policy.set(policy)
    try:
        checker = make_yolo_inheritance_checker()
        assert checker(type("T", (), {"name": "Read"})()) is True
        assert checker(type("T", (), {"name": "Bash"})()) is False
    finally:
        current_permission_policy.reset(token)
