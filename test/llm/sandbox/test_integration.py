"""Platform-conditional integration tests: real OS-sandboxed shell commands.

These spawn actual subprocesses under sandbox-exec (macOS) or bwrap (Linux)
and are skipped where the mechanism is unavailable.
"""

from __future__ import annotations

import os
import platform
import shutil

import pytest

from zrb.llm.sandbox import SandboxPolicy, current_sandbox_policy
from zrb.llm.tool.shell import run_shell_command

needs_seatbelt = pytest.mark.skipif(
    platform.system() != "Darwin" or not shutil.which("sandbox-exec"),
    reason="requires macOS with sandbox-exec",
)
needs_bwrap = pytest.mark.skipif(
    platform.system() != "Linux" or not shutil.which("bwrap"),
    reason="requires Linux with bwrap",
)
needs_any_sandbox = pytest.mark.skipif(
    not (
        (platform.system() == "Darwin" and shutil.which("sandbox-exec"))
        or (platform.system() == "Linux" and shutil.which("bwrap"))
    ),
    reason="requires an OS sandbox mechanism (sandbox-exec or bwrap)",
)


def _policy(tmp_path, **kwargs):
    defaults = {
        "enabled": True,
        "writable_paths": (str(tmp_path / "proj"),),
        "deny_read_paths": (),
    }
    defaults.update(kwargs)
    return SandboxPolicy(**defaults)


@pytest.fixture
def outside_dir():
    """A directory outside every writable root.

    pytest's tmp_path lives under the system temp dir — which the sandbox
    keeps writable by design — so escape tests need a target elsewhere.
    """
    import shutil as _shutil
    import uuid

    path = os.path.join(
        os.path.expanduser("~"), f".zrb-sandbox-test-{uuid.uuid4().hex[:8]}"
    )
    os.makedirs(path, exist_ok=True)
    try:
        yield path
    finally:
        _shutil.rmtree(path, ignore_errors=True)


@pytest.mark.asyncio
@needs_any_sandbox
async def test_write_inside_writable_root_succeeds(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    token = current_sandbox_policy.set(_policy(tmp_path))
    try:
        result = await run_shell_command(
            f"echo content > {proj}/out.txt && cat {proj}/out.txt"
        )
    finally:
        current_sandbox_policy.reset(token)
    assert "content" in result
    assert "Exit Code: 0" in result
    assert (proj / "out.txt").read_text().strip() == "content"


@pytest.mark.asyncio
@needs_any_sandbox
async def test_write_outside_writable_root_fails(tmp_path, outside_dir):
    proj = tmp_path / "proj"
    proj.mkdir()
    token = current_sandbox_policy.set(_policy(tmp_path))
    try:
        result = await run_shell_command(f"echo owned > {outside_dir}/pwned.txt")
    finally:
        current_sandbox_policy.reset(token)
    assert "Exit Code: 0" not in result
    assert not os.path.exists(os.path.join(outside_dir, "pwned.txt"))


@pytest.mark.asyncio
@needs_any_sandbox
async def test_read_of_denied_directory_fails(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "id_rsa").write_text("PRIVATE KEY")
    token = current_sandbox_policy.set(
        _policy(tmp_path, deny_read_paths=(str(secrets),))
    )
    try:
        result = await run_shell_command(f"cat {secrets}/id_rsa")
    finally:
        current_sandbox_policy.reset(token)
    assert "PRIVATE KEY" not in result
    assert "Exit Code: 0" not in result


@pytest.mark.asyncio
@needs_any_sandbox
async def test_skip_sandbox_escape_hatch_works(tmp_path, outside_dir):
    proj = tmp_path / "proj"
    proj.mkdir()
    token = current_sandbox_policy.set(_policy(tmp_path))
    try:
        result = await run_shell_command(
            f"echo escaped > {outside_dir}/ok.txt",
            dangerously_skip_sandbox=True,
        )
    finally:
        current_sandbox_policy.reset(token)
    assert "Exit Code: 0" in result
    assert "[NOTE] executed outside the sandbox" in result
    assert os.path.exists(os.path.join(outside_dir, "ok.txt"))


@pytest.mark.asyncio
@needs_any_sandbox
async def test_timeout_kill_still_terminates_under_sandbox(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    token = current_sandbox_policy.set(_policy(tmp_path))
    try:
        result = await run_shell_command("sleep 30", timeout=2)
    finally:
        current_sandbox_policy.reset(token)
    assert "timed out" in result.lower()


@pytest.mark.asyncio
@needs_any_sandbox
async def test_no_spurious_background_pids_under_sandbox(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    token = current_sandbox_policy.set(_policy(tmp_path))
    try:
        result = await run_shell_command("echo done")
    finally:
        current_sandbox_policy.reset(token)
    assert "Background PIDs: (none)" in result


@pytest.mark.asyncio
@needs_any_sandbox
async def test_background_pids_still_detected_under_sandbox(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    token = current_sandbox_policy.set(_policy(tmp_path))
    try:
        result = await run_shell_command("sleep 3 & echo started")
    finally:
        current_sandbox_policy.reset(token)
    assert "started" in result
    assert "Background PIDs: (none)" not in result


@pytest.mark.asyncio
@needs_any_sandbox
async def test_network_stays_open_in_v1(tmp_path):
    """v1 isolates the filesystem only; sockets must not be blocked."""
    proj = tmp_path / "proj"
    proj.mkdir()
    token = current_sandbox_policy.set(_policy(tmp_path))
    try:
        result = await run_shell_command(
            "python3 -c \"import socket; s=socket.socket(); s.close(); print('sock-ok')\""
        )
    finally:
        current_sandbox_policy.reset(token)
    assert "sock-ok" in result


@pytest.mark.asyncio
async def test_disabled_sandbox_leaves_shell_untouched(tmp_path):
    """Default-off invariant for the shell tool."""
    out = tmp_path / "anywhere.txt"
    result = await run_shell_command(f"echo free > {out}")
    assert "Exit Code: 0" in result
    assert out.exists()
    assert os.path.exists(out)
