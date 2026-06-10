"""Tests for the sandbox execution gate in ``zrb.llm.agent.common``."""

from __future__ import annotations

import pytest

from zrb.llm.permission import Capability, tag
from zrb.llm.sandbox import SandboxPolicy, current_sandbox_policy
from zrb.llm.sandbox.state import (
    get_current_sandbox_policy,
    get_effective_sandbox_policy,
    set_current_sandbox_policy,
)

# --- state ------------------------------------------------------------------


def test_effective_policy_defaults_to_config_disabled():
    assert get_effective_sandbox_policy().enabled is False


def test_explicit_policy_wins():
    policy = SandboxPolicy(enabled=True)
    token = current_sandbox_policy.set(policy)
    try:
        assert get_effective_sandbox_policy() is policy
    finally:
        current_sandbox_policy.reset(token)


def test_public_setters_and_getters_round_trip():
    policy = SandboxPolicy(enabled=True)
    set_current_sandbox_policy(policy)
    try:
        assert get_current_sandbox_policy() is policy
    finally:
        set_current_sandbox_policy(None)


# --- gate via create_safe_wrapper -------------------------------------------


def _outside_path():
    """A path outside every writable root (cwd, tempdir, the policy's roots)."""
    import os

    return os.path.join(os.path.expanduser("~"), "zrb-test-elsewhere", "x.txt")


def _enabled_policy(tmp_path, **kwargs):
    defaults = {
        "enabled": True,
        "writable_paths": (str(tmp_path / "proj"),),
        "deny_read_paths": (),
    }
    defaults.update(kwargs)
    return SandboxPolicy(**defaults)


@pytest.mark.asyncio
async def test_gate_inert_when_disabled(tmp_path):
    """Default-off invariant: no opt-in → tool runs exactly as before."""
    from zrb.llm.agent.common import create_safe_wrapper

    def mutate(path: str = ""):
        return "did it"

    tag(mutate, Capability.EDIT)
    wrapped = create_safe_wrapper(mutate)
    result = await wrapped(path="/definitely/outside/file.txt")
    assert result.content == "did it"
    assert "blocked" not in result.metadata


@pytest.mark.asyncio
async def test_gate_blocks_edit_outside_writable_roots(tmp_path):
    from zrb.llm.agent.common import create_safe_wrapper

    calls = []

    def mutate(path: str = ""):
        calls.append(path)
        return "did it"

    tag(mutate, Capability.EDIT)
    wrapped = create_safe_wrapper(mutate)

    token = current_sandbox_policy.set(_enabled_policy(tmp_path))
    try:
        # NOTE: tmp_path is inside the always-writable system temp dir, so the
        # "outside" target must live elsewhere (no write actually happens).
        result = await wrapped(path=_outside_path())
    finally:
        current_sandbox_policy.reset(token)

    assert result.metadata.get("blocked") is True
    assert "Blocked by sandbox policy" in result.content
    assert calls == []  # never executed


@pytest.mark.asyncio
async def test_gate_allows_edit_inside_writable_roots(tmp_path):
    from zrb.llm.agent.common import create_safe_wrapper

    (tmp_path / "proj").mkdir()

    def mutate(path: str = ""):
        return "did it"

    tag(mutate, Capability.EDIT)
    wrapped = create_safe_wrapper(mutate)

    token = current_sandbox_policy.set(_enabled_policy(tmp_path))
    try:
        result = await wrapped(path=str(tmp_path / "proj" / "x.txt"))
    finally:
        current_sandbox_policy.reset(token)

    assert result.content == "did it"
    assert "blocked" not in result.metadata


@pytest.mark.asyncio
async def test_gate_blocks_read_of_deny_root(tmp_path):
    from zrb.llm.agent.common import create_safe_wrapper

    secrets = tmp_path / "secrets"
    secrets.mkdir()

    def read(path: str = ""):
        return "content"

    tag(read, Capability.READ)
    wrapped = create_safe_wrapper(read)

    policy = _enabled_policy(tmp_path, deny_read_paths=(str(secrets),))
    token = current_sandbox_policy.set(policy)
    try:
        result = await wrapped(path=str(secrets / "id_rsa"))
    finally:
        current_sandbox_policy.reset(token)

    assert result.metadata.get("blocked") is True


@pytest.mark.asyncio
async def test_gate_does_not_path_check_execute_tools(tmp_path):
    """Shell is the OS sandbox layer's territory, not argument inspection."""
    from zrb.llm.agent.common import create_safe_wrapper

    def run(command: str = "", path: str = ""):
        return "ran"

    tag(run, Capability.EXECUTE)
    wrapped = create_safe_wrapper(run)

    token = current_sandbox_policy.set(_enabled_policy(tmp_path))
    try:
        result = await wrapped(command="rm -rf /", path="/outside/x")
    finally:
        current_sandbox_policy.reset(token)

    assert result.content == "ran"
    assert "blocked" not in result.metadata


@pytest.mark.asyncio
async def test_gate_write_checks_untagged_tools(tmp_path):
    """UNKNOWN capability (e.g. MCP tools) is write-checked — safe by default."""
    from zrb.llm.agent.common import create_safe_wrapper

    def mystery(path: str = ""):
        return "did it"

    wrapped = create_safe_wrapper(mystery)

    token = current_sandbox_policy.set(_enabled_policy(tmp_path))
    try:
        result = await wrapped(path=_outside_path())
    finally:
        current_sandbox_policy.reset(token)

    assert result.metadata.get("blocked") is True


@pytest.mark.asyncio
async def test_gate_blocks_escape_when_disallowed(tmp_path):
    from zrb.llm.agent.common import create_safe_wrapper

    def run(command: str = "", dangerously_skip_sandbox: bool = False):
        return "ran"

    tag(run, Capability.EXECUTE)
    wrapped = create_safe_wrapper(run)

    policy = _enabled_policy(tmp_path, allow_escape=False)
    token = current_sandbox_policy.set(policy)
    try:
        result = await wrapped(command="ls", dangerously_skip_sandbox=True)
    finally:
        current_sandbox_policy.reset(token)

    assert result.metadata.get("blocked") is True
    assert "dangerously_skip_sandbox" in result.content


@pytest.mark.asyncio
async def test_gate_move_checks_src_and_dst(tmp_path):
    from zrb.llm.agent.common import create_safe_wrapper

    (tmp_path / "proj").mkdir()

    def move(src: str = "", dst: str = ""):
        return "moved"

    tag(move, Capability.EDIT)
    wrapped = create_safe_wrapper(move)

    token = current_sandbox_policy.set(_enabled_policy(tmp_path))
    try:
        # src inside, dst outside → blocked
        blocked = await wrapped(
            src=str(tmp_path / "proj" / "a.txt"),
            dst=_outside_path(),
        )
        # both inside → allowed
        allowed = await wrapped(
            src=str(tmp_path / "proj" / "a.txt"),
            dst=str(tmp_path / "proj" / "b.txt"),
        )
    finally:
        current_sandbox_policy.reset(token)

    assert blocked.metadata.get("blocked") is True
    assert allowed.content == "moved"
