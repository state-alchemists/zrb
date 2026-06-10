"""Dispatch-matrix tests for build_sandboxed_argv."""

from __future__ import annotations

import pytest

from zrb.llm.sandbox import (
    ESCAPE_NOTE,
    SandboxPolicy,
    SandboxUnavailableError,
    build_sandboxed_argv,
)
from zrb.llm.sandbox import os_sandbox as os_sandbox_module

PLAIN = ["bash", "-c", "echo hi"]


def _call(policy, skip=False):
    return build_sandboxed_argv("bash", "-c", "echo hi", "", policy, skip=skip)


def _patch_platform(monkeypatch, system):
    monkeypatch.setattr(os_sandbox_module.platform, "system", lambda: system)


def test_disabled_policy_is_passthrough(monkeypatch):
    _patch_platform(monkeypatch, "Darwin")
    argv, note = _call(SandboxPolicy(enabled=False))
    assert argv == PLAIN
    assert note is None


def test_os_shell_off_is_passthrough(monkeypatch):
    _patch_platform(monkeypatch, "Darwin")
    argv, note = _call(SandboxPolicy(enabled=True, os_shell="off"))
    assert argv == PLAIN
    assert note is None


def test_darwin_wraps_with_sandbox_exec(monkeypatch, tmp_path):
    _patch_platform(monkeypatch, "Darwin")
    monkeypatch.setattr(
        os_sandbox_module.shutil, "which", lambda name: "/usr/bin/sandbox-exec"
    )
    policy = SandboxPolicy(enabled=True, writable_paths=(str(tmp_path),))
    argv, note = _call(policy)
    assert argv[0] == "/usr/bin/sandbox-exec"
    assert argv[1] == "-p"
    assert "(deny file-write*)" in argv[2]
    assert argv[3:] == PLAIN
    assert note is None


def test_darwin_without_sandbox_exec_warns(monkeypatch, tmp_path):
    _patch_platform(monkeypatch, "Darwin")
    monkeypatch.setattr(os_sandbox_module.shutil, "which", lambda name: None)
    policy = SandboxPolicy(enabled=True, writable_paths=(str(tmp_path),))
    argv, note = _call(policy)
    assert argv == PLAIN
    assert note is not None and "WARNING" in note


def test_linux_wraps_with_bwrap(monkeypatch, tmp_path):
    _patch_platform(monkeypatch, "Linux")
    monkeypatch.setattr(
        os_sandbox_module.shutil, "which", lambda name: "/usr/bin/bwrap"
    )
    policy = SandboxPolicy(enabled=True, writable_paths=(str(tmp_path),))
    argv, note = _call(policy)
    assert argv[0] == "/usr/bin/bwrap"
    assert argv[-3:] == PLAIN
    assert argv[argv.index("--") :] == ["--", *PLAIN]
    assert note is None


def test_linux_without_bwrap_warn_mode(monkeypatch, tmp_path):
    _patch_platform(monkeypatch, "Linux")
    monkeypatch.setattr(os_sandbox_module.shutil, "which", lambda name: None)
    policy = SandboxPolicy(
        enabled=True, writable_paths=(str(tmp_path),), fallback="warn"
    )
    argv, note = _call(policy)
    assert argv == PLAIN
    assert "bwrap" in note


def test_linux_without_bwrap_deny_mode(monkeypatch, tmp_path):
    _patch_platform(monkeypatch, "Linux")
    monkeypatch.setattr(os_sandbox_module.shutil, "which", lambda name: None)
    policy = SandboxPolicy(
        enabled=True, writable_paths=(str(tmp_path),), fallback="deny"
    )
    with pytest.raises(SandboxUnavailableError):
        _call(policy)


def test_windows_warn_mode_is_not_silent(monkeypatch, tmp_path):
    _patch_platform(monkeypatch, "Windows")
    policy = SandboxPolicy(
        enabled=True, writable_paths=(str(tmp_path),), fallback="warn"
    )
    argv, note = _call(policy)
    assert argv == PLAIN
    assert note is not None and "WITHOUT OS-level isolation" in note


def test_windows_deny_mode_refuses(monkeypatch, tmp_path):
    _patch_platform(monkeypatch, "Windows")
    policy = SandboxPolicy(
        enabled=True, writable_paths=(str(tmp_path),), fallback="deny"
    )
    with pytest.raises(SandboxUnavailableError):
        _call(policy)


def test_skip_with_escape_allowed(monkeypatch, tmp_path):
    _patch_platform(monkeypatch, "Darwin")
    policy = SandboxPolicy(
        enabled=True, writable_paths=(str(tmp_path),), allow_escape=True
    )
    argv, note = _call(policy, skip=True)
    assert argv == PLAIN
    assert note == ESCAPE_NOTE


def test_skip_with_escape_disallowed(monkeypatch, tmp_path):
    _patch_platform(monkeypatch, "Darwin")
    policy = SandboxPolicy(
        enabled=True, writable_paths=(str(tmp_path),), allow_escape=False
    )
    with pytest.raises(SandboxUnavailableError):
        _call(policy, skip=True)


def test_unrepresentable_profile_path_falls_back(monkeypatch):
    _patch_platform(monkeypatch, "Darwin")
    monkeypatch.setattr(
        os_sandbox_module.shutil, "which", lambda name: "/usr/bin/sandbox-exec"
    )
    policy = SandboxPolicy(
        enabled=True, writable_paths=("/tmp/bad\npath",), fallback="warn"
    )
    argv, note = _call(policy)
    assert argv == PLAIN
    assert "cannot generate sandbox profile" in note
