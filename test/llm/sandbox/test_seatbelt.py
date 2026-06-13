"""Golden tests for SBPL profile generation."""

from __future__ import annotations

import os

import pytest

from zrb.llm.sandbox import SandboxPolicy
from zrb.llm.sandbox.seatbelt import _sbpl_quote, build_sbpl


def test_profile_structure(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    policy = SandboxPolicy(
        enabled=True,
        writable_paths=(str(proj),),
        deny_read_paths=(str(secrets),),
    )
    profile = build_sbpl(policy)
    lines = profile.splitlines()
    assert lines[0] == "(version 1)"
    assert lines[1] == "(allow default)"
    assert lines[2] == "(deny file-write*)"
    # Writable roots are realpath'd subpaths inside the allow clause.
    assert f'  (subpath "{os.path.realpath(str(proj))}")' in lines
    # Device literals stay writable for non-interactive shells.
    assert '  (literal "/dev/null")' in lines
    # Deny-read clause covers the secret dir.
    assert "(deny file-read* file-read-metadata" in profile
    assert f'"{os.path.realpath(str(secrets))}"' in profile


def test_profile_omits_deny_clause_when_no_roots_exist(tmp_path):
    policy = SandboxPolicy(
        enabled=True,
        writable_paths=(str(tmp_path),),
        deny_read_paths=(str(tmp_path / "ghost"),),
    )
    profile = build_sbpl(policy)
    assert "file-read" not in profile


def test_quote_escapes_backslash_and_quotes():
    assert _sbpl_quote('/a/"b"') == '"/a/\\"b\\""'
    assert _sbpl_quote("/a/b\\c") == '"/a/b\\\\c"'


def test_quote_refuses_newline():
    with pytest.raises(ValueError):
        _sbpl_quote("/a/b\nc")


def test_writable_paths_with_newline_fall_back(tmp_path):
    # A profile-unrepresentable path must not produce a broken profile.
    policy = SandboxPolicy(
        enabled=True,
        writable_paths=(str(tmp_path) + "\nmalicious",),
        deny_read_paths=(),
    )
    with pytest.raises(ValueError):
        build_sbpl(policy)
