"""Sandbox gate: the path-argument spellings an MCP server or plugin uses.

`pattern` belongs to this group without being a path: a glob-shaped tool joins it
onto one, and an absolute pattern replaces that path outright, so the gate judges
it as a path too.

Split out of `test_gate.py` (feature group: argument spellings), which had
crossed the 500-line test-file threshold.
"""

from __future__ import annotations

import os

import pytest

from zrb.llm.capabilities.permission import Capability, tag
from zrb.llm.capabilities.permission.policy import PATH_ARG_KEYS
from zrb.llm.capabilities.sandbox import SandboxPolicy, current_sandbox_policy


def _enabled_policy(tmp_path, **kwargs):
    """The same enabled policy `test_gate.py` builds, mirrored to keep this
    feature group standalone."""
    defaults = {
        "enabled": True,
        "writable_paths": (str(tmp_path / "proj"),),
        "deny_read_paths": (),
    }
    defaults.update(kwargs)
    return SandboxPolicy(**defaults)


# --- gate: argument spellings an MCP server or plugin uses ------------------
#
# zrb's own tools declare snake_case (`file_path`, `src`, `dst`); an MCP server
# or plugin may declare `filePath`, `sourcePath`, `directory`, `target`, and so
# on. A key the gate does not know is a call it never checks, so every spelling
# in the shared `PATH_ARG_KEYS` list is covered here one by one.


@pytest.mark.parametrize("capability", [Capability.EDIT, Capability.UNKNOWN])
@pytest.mark.parametrize("key", PATH_ARG_KEYS)
@pytest.mark.asyncio
async def test_gate_write_checks_an_mcp_style_path_key(
    tmp_path, outside_root, key, capability
):
    """EDIT/UNKNOWN tools are write-checked whatever the path key is called."""
    from zrb.llm.engine.agent.common import create_safe_wrapper

    calls = []

    def mutate(**kwargs):
        calls.append(kwargs)
        return "did it"

    tag(mutate, capability)
    wrapped = create_safe_wrapper(mutate)

    token = current_sandbox_policy.set(_enabled_policy(tmp_path))
    try:
        result = await wrapped(**{key: str(outside_root / "x.txt")})
    finally:
        current_sandbox_policy.reset(token)

    assert result.metadata.get("blocked") is True
    assert calls == []


@pytest.mark.parametrize("key", PATH_ARG_KEYS)
@pytest.mark.asyncio
async def test_gate_read_checks_an_mcp_style_path_key(tmp_path, key):
    """A READ tool whose path key is an MCP-style spelling is denied too."""
    from zrb.llm.engine.agent.common import create_safe_wrapper

    secrets = tmp_path / "secrets"
    secrets.mkdir()

    def read(**kwargs):
        return "content"

    tag(read, Capability.READ)
    wrapped = create_safe_wrapper(read)
    policy = _enabled_policy(tmp_path, deny_read_paths=(str(secrets),))

    token = current_sandbox_policy.set(policy)
    try:
        result = await wrapped(**{key: str(secrets / "id_rsa")})
    finally:
        current_sandbox_policy.reset(token)

    assert result.metadata.get("blocked") is True


@pytest.mark.parametrize("capability", [Capability.EDIT, Capability.UNKNOWN])
@pytest.mark.asyncio
async def test_gate_write_checks_source_path_outside_writable_roots(
    tmp_path, outside_root, capability
):
    """`sourcePath` was in neither list, so a copy out of the workspace ran."""
    from zrb.llm.engine.agent.common import create_safe_wrapper

    calls = []

    def copy_file(sourcePath: str = ""):
        calls.append(sourcePath)
        return "did it"

    tag(copy_file, capability)
    wrapped = create_safe_wrapper(copy_file)

    token = current_sandbox_policy.set(_enabled_policy(tmp_path))
    try:
        result = await wrapped(sourcePath=str(outside_root / "x.txt"))
    finally:
        current_sandbox_policy.reset(token)

    assert result.metadata.get("blocked") is True
    assert calls == []


@pytest.mark.asyncio
async def test_gate_read_checks_a_glob_pattern(tmp_path):
    """`Glob` joins `pattern` onto `path`, and an absolute pattern replaces it.

    The `path` argument alone is not what the search opens, so the pattern is
    judged as a path too: one naming a protected file is refused before the glob
    runs, whatever the tool does with it afterwards.
    """
    from zrb.llm.capabilities.sandbox.state import sandbox_policy
    from zrb.llm.engine.agent.common import create_safe_wrapper

    project = tmp_path / "proj"
    project.mkdir()
    secrets = tmp_path / "secrets"
    secrets.mkdir()

    def glob_files(pattern: str = "", path: str = ""):
        return "matches"

    tag(glob_files, Capability.READ)
    wrapped = create_safe_wrapper(glob_files, name="Glob")
    policy = _enabled_policy(tmp_path, deny_read_paths=(str(secrets),))
    with sandbox_policy(policy):
        blocked = await wrapped(
            pattern=os.path.join(str(secrets), "id_*"), path=str(project)
        )
        allowed = await wrapped(pattern="**/*.py", path=str(project))

    assert blocked.metadata.get("blocked") is True
    assert allowed.return_value == "matches"


@pytest.mark.asyncio
async def test_gate_ignores_a_call_with_no_path_like_argument(tmp_path):
    """No path-like argument means nothing to judge — unchanged behavior."""
    from zrb.llm.engine.agent.common import create_safe_wrapper

    def query(sql: str = "", content: str = ""):
        return "rows"

    tag(query, Capability.EDIT)
    wrapped = create_safe_wrapper(query)

    token = current_sandbox_policy.set(_enabled_policy(tmp_path))
    try:
        result = await wrapped(sql="select 1", content="inline text")
    finally:
        current_sandbox_policy.reset(token)

    assert result.return_value == "rows"
    assert "blocked" not in result.metadata
