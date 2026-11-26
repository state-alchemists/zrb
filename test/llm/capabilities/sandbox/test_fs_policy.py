"""Tests for the Python-level filesystem checks (check_read / check_write)."""

from __future__ import annotations

import os

import pytest

from zrb.llm.capabilities.sandbox import (
    SandboxPolicy,
    check_read,
    check_write,
    contains_denied_read_root,
    is_read_allowed,
)
from zrb.llm.capabilities.sandbox.fs_policy import is_read_within, is_write_within


def _volume_ignores_case(directory) -> bool:
    """Whether *directory*'s volume treats a case variant as the same entry.

    Asked of a path that already exists under a different casing, so no probe
    file is written: a volume that keeps the two spellings apart answers with an
    error, which is the answer this asks for.
    """
    spelling = str(directory)
    try:
        return os.stat(spelling.swapcase()).st_ino == os.stat(spelling).st_ino
    except OSError:
        return False


# --- is_read_within / is_write_within ---------------------------------------


def test_is_read_within_subpath():
    assert is_read_within("/a/b/c", "/a/b") is True


def test_is_read_within_rejects_sibling_prefix():
    # "/a/bc" shares a string prefix with "/a/b" but is not inside it.
    assert is_read_within("/a/bc", "/a/b") is False


def test_is_read_within_mixed_abs_rel_is_false():
    # commonpath raises ValueError on mixed absolute/relative (and on
    # cross-drive comparisons on Windows) — treated as "not within".
    assert is_read_within("relative/path", "/abs/root") is False


def test_is_write_within_subpath():
    assert is_write_within("/a/b/c", "/a/b") is True


def test_is_write_within_rejects_sibling_prefix():
    assert is_write_within("/a/bc", "/a/b") is False


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


def test_write_outside_root_blocked(tmp_path, outside_root):
    # NOTE: the system temp dir is always writable by design, so `outside_root`
    # narrows it to a sibling.
    (tmp_path / "proj").mkdir()
    policy = _policy(tmp_path)
    outside = str(outside_root / "f.txt")
    error = check_write(outside, policy)
    assert error is not None
    assert "outside the sandbox writable roots" in error


def test_symlink_escape_is_blocked(tmp_path, outside_root):
    proj = tmp_path / "proj"
    proj.mkdir()
    # The escape target must be outside every writable root (incl. tempdir).
    (proj / "esc").symlink_to(outside_root)
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


# --- is_read_allowed (the per-file form recursive readers use) -------------


def test_is_read_allowed_refuses_a_file_inside_a_deny_root(tmp_path):
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    policy = _policy(tmp_path, deny_read_paths=(str(secrets),))
    assert is_read_allowed(str(secrets / "id_rsa"), policy) is False


def test_is_read_allowed_accepts_a_file_outside_every_deny_root(tmp_path):
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    policy = _policy(tmp_path, deny_read_paths=(str(secrets),))
    assert is_read_allowed(str(tmp_path / "proj" / "main.py"), policy) is True


def test_a_disabled_policy_allows_every_read(tmp_path):
    """The no-sandbox path stays exactly as it was: off means no filtering."""
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    policy = SandboxPolicy(
        enabled=False,
        writable_paths=(str(tmp_path / "proj"),),
        deny_read_paths=(str(secrets),),
    )
    assert is_read_allowed(str(secrets / "id_rsa"), policy) is True


# --- contains_denied_read_root (a parent of a deny root) --------------------


def test_contains_denied_read_root_finds_the_root_under_the_path(tmp_path):
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    policy = _policy(tmp_path, deny_read_paths=(str(secrets),))
    assert contains_denied_read_root(str(tmp_path), policy) == os.path.realpath(
        str(secrets)
    )


def test_contains_denied_read_root_ignores_a_sibling(tmp_path):
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    project = tmp_path / "proj"
    project.mkdir()
    policy = _policy(tmp_path, deny_read_paths=(str(secrets),))
    assert contains_denied_read_root(str(project), policy) is None


def test_a_disabled_policy_contains_no_denied_read_root(tmp_path):
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    policy = SandboxPolicy(
        enabled=False,
        writable_paths=(str(tmp_path / "proj"),),
        deny_read_paths=(str(secrets),),
    )
    assert contains_denied_read_root(str(tmp_path), policy) is None


# --- casing ---------------------------------------------------------------
#
# `os.path.normcase` is the identity on POSIX, so a spelled-once comparison let
# casing defeat the deny list: on macOS's default case-insensitive volume
# `realpath` keeps the caller's casing, and `~/.SSH/KNOWN_HOSTS` compared as
# outside `~/.ssh` while being the same file. The two volumes need different
# answers, so each test skips on the one it cannot speak about.


def test_a_case_variant_of_a_deny_root_is_refused(tmp_path):
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "id_rsa").write_text("KEY")
    if not _volume_ignores_case(tmp_path):
        pytest.skip("this volume keeps the two spellings apart")
    policy = _policy(tmp_path, deny_read_paths=(str(secrets),))

    error = check_read(str(secrets / "id_rsa").upper(), policy)

    assert error is not None
    assert "may not be read" in error


def test_a_case_variant_of_a_deny_root_is_not_writable(tmp_path):
    """A secret you cannot read you also cannot plant, whatever its casing."""
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    if not _volume_ignores_case(tmp_path):
        pytest.skip("this volume keeps the two spellings apart")
    policy = _policy(tmp_path, deny_read_paths=(str(secrets),))

    error = check_write(os.path.join(str(secrets).upper(), "authorized_keys"), policy)

    assert error is not None
    assert "protected directory" in error


def test_a_case_variant_parent_is_seen_by_the_containment_check(tmp_path):
    """A recursive read of the parent under another casing opens the root too."""
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    if not _volume_ignores_case(tmp_path):
        pytest.skip("this volume keeps the two spellings apart")
    policy = _policy(tmp_path, deny_read_paths=(str(secrets),))

    contained = contains_denied_read_root(str(tmp_path).upper(), policy)

    assert contained == os.path.realpath(str(secrets))


def test_an_unborn_file_under_a_case_variant_root_is_refused(tmp_path):
    """Nothing exists at the tail, so the folded spelling has the last word.

    Holds on both volumes: on a case-insensitive one the parent's inode names
    the root, and on a case-sensitive one the fold still reaches it and a read
    errs toward refusing.
    """
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    policy = _policy(tmp_path, deny_read_paths=(str(secrets),))

    error = check_read(os.path.join(str(secrets).upper(), "UNBORN_KEY"), policy)

    assert error is not None
    assert "may not be read" in error


def test_a_cased_sibling_reads_freely_on_a_case_sensitive_volume(tmp_path):
    """`SECRETS` and `secrets` are two directories where the volume says so."""
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    if _volume_ignores_case(tmp_path):
        pytest.skip("this volume folds the two spellings onto one directory")
    sibling = tmp_path / "SECRETS"
    sibling.mkdir()
    (sibling / "note.txt").write_text("not a secret")
    policy = _policy(tmp_path, deny_read_paths=(str(secrets),))

    assert check_read(str(sibling / "note.txt"), policy) is None
