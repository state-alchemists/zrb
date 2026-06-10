"""Golden tests for bubblewrap argument generation."""

from __future__ import annotations

import os

from zrb.llm.sandbox import SandboxPolicy
from zrb.llm.sandbox.bwrap import build_bwrap_argv


def test_argv_structure(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    secret_file = tmp_path / "token.txt"
    secret_file.write_text("secret")
    policy = SandboxPolicy(
        enabled=True,
        writable_paths=(str(proj),),
        deny_read_paths=(str(secrets), str(secret_file)),
    )
    argv = build_bwrap_argv("/usr/bin/bwrap", policy)

    assert argv[0] == "/usr/bin/bwrap"
    assert "--die-with-parent" in argv
    # Read-only root, then dev/proc.
    ro_root = argv.index("--ro-bind")
    assert argv[ro_root + 1 : ro_root + 3] == ["/", "/"]
    assert "--dev-bind" in argv
    assert "--proc" in argv
    # Writable root is bound read-write.
    proj_real = os.path.realpath(str(proj))
    bind_idx = argv.index("--bind")
    assert argv[bind_idx + 1 : bind_idx + 3] == [proj_real, proj_real]
    # Deny-read dir masked with tmpfs; deny-read file masked with /dev/null.
    assert "--tmpfs" in argv
    assert argv[argv.index("--tmpfs") + 1] == os.path.realpath(str(secrets))
    null_binds = [
        argv[i + 1 : i + 3] for i, a in enumerate(argv) if a == "--ro-bind"
    ]
    assert ["/dev/null", os.path.realpath(str(secret_file))] in null_binds
    # Ends with the argv separator.
    assert argv[-1] == "--"


def test_no_network_or_pid_unsharing(tmp_path):
    policy = SandboxPolicy(enabled=True, writable_paths=(str(tmp_path),))
    argv = build_bwrap_argv("bwrap", policy)
    assert "--unshare-net" not in argv
    assert "--unshare-pid" not in argv


def test_masks_come_after_writable_binds(tmp_path):
    """A deny-read dir inside a writable root must stay masked (mount order)."""
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    policy = SandboxPolicy(
        enabled=True,
        writable_paths=(str(tmp_path),),
        deny_read_paths=(str(secrets),),
    )
    argv = build_bwrap_argv("bwrap", policy)
    assert argv.index("--tmpfs") > argv.index("--bind")
