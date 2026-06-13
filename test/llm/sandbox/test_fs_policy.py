"""Tests for the Python-level filesystem checks (check_read / check_write)."""

from __future__ import annotations

import os

from zrb.llm.sandbox import SandboxPolicy, check_read, check_write
from zrb.llm.sandbox.fs_policy import _is_within

# --- _is_within -----------------------------------------------------------


def test_is_within_subpath():
    assert _is_within("/a/b/c", "/a/b") is True


def test_is_within_rejects_sibling_prefix():
    # "/a/bc" shares a string prefix with "/a/b" but is not inside it.
    assert _is_within("/a/bc", "/a/b") is False


def test_is_within_mixed_abs_rel_is_false():
    # commonpath raises ValueError on mixed absolute/relative (and on
    # cross-drive comparisons on Windows) — treated as "not within".
    assert _is_within("relative/path", "/abs/root") is False


# --- check_write ----------------------------------------------------------


def _policy(tmp_path, **kwargs):
    defaults = {
        "enabled": True,
        "writable_paths": (str(tmp_path / "proj"),),
        "deny_read_paths": (),
    }
    defaults.update(kwargs)
    return SandboxPolicy(**defaults)


def test_write_inside_root_allowed(tmp_path):
    (tmp_path / "proj").mkdir()
    policy = _policy(tmp_path)
    assert check_write(str(tmp_path / "proj" / "file.txt"), policy) is None


def test_write_to_nonexistent_nested_target_inside_root_allowed(tmp_path):
    (tmp_path / "proj").mkdir()
    policy = _policy(tmp_path)
    target = tmp_path / "proj" / "new" / "deep" / "file.txt"
    assert check_write(str(target), policy) is None


def test_write_outside_root_blocked(tmp_path):
    # NOTE: pytest's tmp_path lives under the system temp dir, which is always
    # writable by design — "outside" paths must live elsewhere (e.g. $HOME).
    (tmp_path / "proj").mkdir()
    policy = _policy(tmp_path)
    outside = os.path.join(os.path.expanduser("~"), "zrb-test-elsewhere", "f.txt")
    error = check_write(outside, policy)
    assert error is not None
    assert "outside the sandbox writable roots" in error


def test_symlink_escape_is_blocked(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    # The escape target must be outside every writable root (incl. tempdir).
    (proj / "esc").symlink_to(os.path.expanduser("~"))
    policy = _policy(tmp_path)
    error = check_write(str(proj / "esc" / "owned.txt"), policy)
    assert error is not None


def test_write_into_deny_read_root_blocked_even_if_writable(tmp_path):
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    policy = SandboxPolicy(
        enabled=True,
        writable_paths=(str(tmp_path),),
        deny_read_paths=(str(secrets),),
    )
    error = check_write(str(secrets / "authorized_keys"), policy)
    assert error is not None
    assert "protected directory" in error


# --- check_read -----------------------------------------------------------


def test_read_outside_deny_roots_allowed(tmp_path):
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    policy = _policy(tmp_path, deny_read_paths=(str(secrets),))
    assert check_read(str(tmp_path / "proj" / "anything.txt"), policy) is None


def test_read_inside_deny_root_blocked(tmp_path):
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    policy = _policy(tmp_path, deny_read_paths=(str(secrets),))
    error = check_read(str(secrets / "id_rsa"), policy)
    assert error is not None
    assert "may not be read" in error


def test_read_via_symlink_into_deny_root_blocked(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "id_rsa").write_text("KEY")
    (proj / "innocent.txt").symlink_to(secrets / "id_rsa")
    policy = _policy(tmp_path, deny_read_paths=(str(secrets),))
    error = check_read(str(proj / "innocent.txt"), policy)
    assert error is not None


def test_missing_deny_root_is_ignored(tmp_path):
    policy = _policy(tmp_path, deny_read_paths=(str(tmp_path / "ghost"),))
    assert check_read(str(tmp_path / "ghost" / "x"), policy) is None
