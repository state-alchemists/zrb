"""Tests for SandboxPolicy construction and root resolution."""

from __future__ import annotations

import os
import platform
import tempfile

from zrb.llm.sandbox import (
    DEFAULT_DENY_READ_PATHS,
    SandboxPolicy,
    coerce_sandbox,
    resolve_sandbox_policy_from_config,
    resolved_deny_read_roots,
    resolved_writable_roots,
)

# --- config resolution ----------------------------------------------------


def test_default_policy_is_disabled():
    policy = resolve_sandbox_policy_from_config()
    assert policy.enabled is False
    assert policy.os_shell == "auto"
    assert policy.fallback == "warn"
    assert policy.allow_escape is True
    assert policy.writable_paths == ()
    assert len(policy.deny_read_paths) == len(DEFAULT_DENY_READ_PATHS)


def test_env_enables_sandbox(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_SANDBOX_ENABLED", "true")
    monkeypatch.setenv("ZRB_LLM_SANDBOX_FALLBACK", "deny")
    monkeypatch.setenv("ZRB_LLM_SANDBOX_ALLOW_ESCAPE", "false")
    policy = resolve_sandbox_policy_from_config()
    assert policy.enabled is True
    assert policy.fallback == "deny"
    assert policy.allow_escape is False


def test_env_writable_paths_colon_list_expands_user(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_SANDBOX_WRITABLE_PATHS", "~/proj:/var/data")
    policy = resolve_sandbox_policy_from_config()
    assert os.path.expanduser("~/proj") in policy.writable_paths
    assert "/var/data" in policy.writable_paths


def test_env_deny_read_paths_replaces_default(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_SANDBOX_DENY_READ_PATHS", "/etc/secrets")
    policy = resolve_sandbox_policy_from_config()
    assert policy.deny_read_paths == ("/etc/secrets",)


# --- coerce_sandbox -------------------------------------------------------


def test_coerce_none_is_none():
    assert coerce_sandbox(None) is None


def test_coerce_instance_passthrough():
    policy = SandboxPolicy(enabled=True)
    assert coerce_sandbox(policy) is policy


def test_coerce_bool_forces_enabled():
    assert coerce_sandbox(True).enabled is True
    assert coerce_sandbox(False).enabled is False


def test_coerce_unrecognized_is_none():
    assert coerce_sandbox("bogus") is None


# --- resolved_writable_roots ----------------------------------------------


def test_auto_writable_roots_are_cwd_and_tempdir():
    policy = SandboxPolicy(enabled=True)
    roots = resolved_writable_roots(policy)
    assert os.path.realpath(os.getcwd()) in roots
    assert os.path.realpath(tempfile.gettempdir()) in roots


def test_auto_writable_roots_use_explicit_cwd(tmp_path):
    policy = SandboxPolicy(enabled=True)
    roots = resolved_writable_roots(policy, cwd=str(tmp_path))
    assert os.path.realpath(str(tmp_path)) in roots


def test_darwin_auto_roots_include_private_tmp():
    if platform.system() != "Darwin":
        return
    policy = SandboxPolicy(enabled=True)
    assert "/private/tmp" in resolved_writable_roots(policy)


def test_explicit_writable_roots_are_realpathed_and_deduped(tmp_path):
    target = tmp_path / "real"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target)
    policy = SandboxPolicy(
        enabled=True, writable_paths=(str(target), str(link), str(target))
    )
    roots = resolved_writable_roots(policy)
    assert roots[0] == os.path.realpath(str(target))
    assert roots.count(os.path.realpath(str(target))) == 1
    # cwd is NOT writable when explicit roots are pinned…
    assert os.path.realpath(os.getcwd()) not in roots


def test_tempdir_always_writable_even_with_explicit_roots(tmp_path):
    # …but the temp dir always is — the shell PID-tracking wrapper writes there
    # from inside the sandbox.
    policy = SandboxPolicy(enabled=True, writable_paths=(str(tmp_path),))
    roots = resolved_writable_roots(policy)
    assert os.path.realpath(tempfile.gettempdir()) in roots


# --- resolved_deny_read_roots ----------------------------------------------


def test_deny_read_roots_drop_missing_entries(tmp_path):
    existing = tmp_path / "secrets"
    existing.mkdir()
    policy = SandboxPolicy(
        enabled=True,
        deny_read_paths=(str(existing), str(tmp_path / "does-not-exist")),
    )
    assert resolved_deny_read_roots(policy) == (os.path.realpath(str(existing)),)
