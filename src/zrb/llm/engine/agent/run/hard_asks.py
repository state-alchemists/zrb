"""Calls no approval level may cover, whatever the levels say.

Three places answer "may this call run unattended": the tool policy, the
permission policy and yolo. Each of them answers about ordinary calls. Two calls
are not ordinary, because they decide what the machine runs *next* rather than
what it does now:

- A shell call asking to leave the sandbox (ADR-0065). Unsandboxed execution is a
  decision a human makes, which `docs/llm/sandbox.md` states.
- A write to the file the MCP loader reads (ADR-0146). Its `command` reaches
  `StdioTransport`, which starts a host process in a later session — outside
  `build_sandboxed_argv`, the filesystem gate and every approval prompt.

The skip decision asks this before a call is deferred, and the cascade asks it
after, so the answer cannot depend on which path a call happened to take. It is
asked *above* the policy, not beside it: a policy `allow` is an opinion about
ordinary calls, and an allow that quietly covered either of these would be the
same hole one level up.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from zrb.config.config import CFG
from zrb.llm.capabilities.permission.capability import Capability
from zrb.llm.capabilities.permission.policy import PATH_ARG_KEYS
from zrb.llm.capabilities.tool_call.shell_call import is_sandbox_off


def get_llm_tool_name(tool_def: object) -> str:
    """The name a model calls *tool_def* by, or `""` when there is no object."""
    if tool_def is None:
        return ""
    return getattr(tool_def, "name", None) or str(tool_def)


def is_hard_ask_call(tool_name: str, args: Mapping[str, object] | None) -> bool:
    """Whether no auto-approval may cover this call.

    Without arguments there is nothing to judge, and the cascade still asks, so a
    call whose arguments did not parse is left to it rather than guessed at here.
    """
    if not isinstance(args, Mapping):
        return False
    if is_sandbox_off(args):
        return True
    return is_mcp_config_write(tool_name, args)


def is_mcp_config_write(tool_name: str, args: Mapping[str, object]) -> bool:
    """Whether this call would write a file the MCP loader reads.

    A hard ASK rather than a refusal, because the file is ordinary workspace
    content that a user may well mean to edit. Only the capabilities that
    `sandbox_gate` write-checks are judged: a tool that mutates files, and an
    untagged one that might. A shell redirect stays out of reach here, as it does
    for that gate.
    """
    # lazy: tests patch zrb.llm.engine.agent.run.tool_capabilities.get_tool_capability; hoisting bypasses the mock
    from zrb.llm.engine.agent.run.tool_capabilities import get_tool_capability

    if get_tool_capability(tool_name).value not in (
        Capability.EDIT.value,
        Capability.UNKNOWN.value,
    ):
        return False
    return _has_mcp_config_arg(args)


def _has_mcp_config_arg(args: Mapping[str, object]) -> bool:
    """Whether a path-shaped argument of *args* names a config the loader reads."""
    config_paths = _mcp_config_paths()
    for key in PATH_ARG_KEYS:
        value = args.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        if os.path.realpath(os.path.expanduser(value)) in config_paths:
            return True
    return False


def _mcp_config_paths() -> frozenset[str]:
    """Every absolute path `load_mcp_config` reads its config from.

    The loader takes `CFG.MCP_CONFIG_FILE` from the working directory and, when
    that sits under the home directory, from each directory between it and home
    (`capabilities/tool/mcp.py::_get_config_files`). The walk is mirrored rather
    than called: that module imports the MCP client, and an approval decision
    must not pay for it to answer a path question. A config that does not exist
    yet counts — creating one is what this guard is for.
    """
    cwd = os.path.realpath(os.getcwd())
    home = os.path.realpath(os.path.expanduser("~"))
    config_file_name = CFG.MCP_CONFIG_FILE
    if not config_file_name:
        # A blank name reads nothing: `_get_config_files` would test the
        # directory itself and find no file.
        return frozenset()
    directories = {cwd}
    if cwd == home or cwd.startswith(home + os.sep):
        # Every directory between the working directory and home; `home` is an
        # ancestor, so the walk always ends there.
        current = cwd
        while current != home:
            current = os.path.dirname(current)
            directories.add(current)
    return frozenset(
        os.path.realpath(os.path.join(directory, config_file_name))
        for directory in directories
    )


__all__ = ["get_llm_tool_name", "is_hard_ask_call", "is_mcp_config_write"]
