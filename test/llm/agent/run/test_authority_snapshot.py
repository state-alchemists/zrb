"""Tests for capturing ambient authority (zrb.llm.agent.run.authority_snapshot)."""

from __future__ import annotations

from unittest.mock import patch

from zrb.llm.agent.run.authority_snapshot import capture_current_authority
from zrb.llm.agent.run.runner import current_yolo
from zrb.llm.permission.policy import PLAN_MODE_POLICY, PermissionPolicy, Rule
from zrb.llm.permission.state import (
    AgentMode,
    AgentModeState,
    current_agent_mode,
    current_permission_policy,
)
from zrb.llm.sandbox.policy import SandboxPolicy
from zrb.llm.sandbox.state import current_sandbox_policy
from zrb.util.contextvar_scope import scoped


def test_capture_defaults_when_nothing_bound():
    snapshot = capture_current_authority()
    assert snapshot.permission_policy is None
    assert snapshot.yolo is False
    assert snapshot.sandbox_policy is not None
    assert snapshot.sandbox_policy.enabled is False


def test_capture_reads_bound_ambient_state():
    policy = PermissionPolicy(rules=(Rule("*", "deny"),))
    sandbox = SandboxPolicy(enabled=True)
    with (
        scoped(current_permission_policy, policy),
        scoped(current_yolo, True),
        scoped(current_sandbox_policy, sandbox),
    ):
        snapshot = capture_current_authority()

    assert snapshot.permission_policy is policy
    assert snapshot.yolo is True
    assert snapshot.sandbox_policy is sandbox


def test_capture_uses_plan_mode_policy():
    with scoped(current_agent_mode, AgentModeState(mode=AgentMode.PLAN)):
        snapshot = capture_current_authority()

    assert snapshot.permission_policy is PLAN_MODE_POLICY


def test_capture_resolves_configured_sandbox_policy():
    sandbox = SandboxPolicy(enabled=True)
    with scoped(current_sandbox_policy, None):
        with patch(
            "zrb.llm.sandbox.state.resolve_sandbox_policy_from_config",
            return_value=sandbox,
        ):
            snapshot = capture_current_authority()

    assert snapshot.sandbox_policy is sandbox


def test_capture_yolo_override_wins_over_ambient():
    with scoped(current_yolo, True):
        snapshot = capture_current_authority(yolo_override=False)

    assert snapshot.yolo is False


def test_capture_yolo_override_none_falls_back_to_ambient():
    with scoped(current_yolo, True):
        snapshot = capture_current_authority(yolo_override=None)

    assert snapshot.yolo is True
