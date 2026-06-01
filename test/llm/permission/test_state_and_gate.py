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
        set_current_agent_mode(AgentMode.DEFAULT)


def test_explicit_policy_is_returned():
    policy = PermissionPolicy((Rule("*", "allow"),))
    token = current_permission_policy.set(policy)
    try:
        assert get_effective_policy() is policy
    finally:
        current_permission_policy.reset(token)


def test_plan_mode_overrides_explicit_policy():
    from zrb.llm.permission import PLAN_MODE_POLICY

    policy = PermissionPolicy((Rule("*", "allow"),))
    t1 = current_permission_policy.set(policy)
    t2 = current_agent_mode.set(AgentMode.PLAN)
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

    policy = PermissionPolicy(
        (Rule(Capability.EDIT.value, "deny"), Rule("*", "allow"))
    )
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
