import json
import os
import re
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, cast

from zrb.config.config import CFG
from zrb.context.any_context import zrb_print
from zrb.llm.tool.purpose import DECLARED_PURPOSE_KEY, with_declared_purpose
from zrb.llm.tool_call.untrusted_data import UNTRUSTED_DATA_NOTE
from zrb.util.truncate import truncate_text

if TYPE_CHECKING:
    from pydantic_ai import RunContext
    from pydantic_ai.mcp import CallToolFunc, ToolResult
    from pydantic_ai.tools import ToolDefinition
    from pydantic_ai.toolsets.abstract import ToolsetTool

    from zrb.llm.agent.types import AbstractToolset

_ENV_VAR_PATTERN = re.compile(r"\$\{([^}:]+)(:-([^}]*))?\}")
# OpenAI's limit, the strictest provider's; one longer name fails the whole request.
_MAX_TOOL_NAME_LENGTH = 64
# Leaves room for "_" and at least one character of the tool name.
_PREFIX_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,62}")


def load_mcp_config(config_file_name: str | None = None) -> "list[AbstractToolset]":
    if config_file_name is None:
        config_file_name = CFG.MCP_CONFIG_FILE

    config_files = _get_config_files(config_file_name)
    if not config_files:
        return []

    merged_servers = _merge_mcp_servers_config(config_files)
    if not merged_servers:
        return []

    return _create_mcp_toolsets(merged_servers)


def _get_config_files(config_file_name: str) -> list[str]:
    home = os.path.abspath(os.path.expanduser("~"))
    cwd = os.path.abspath(os.getcwd())

    config_files: list[str] = []

    if cwd == home or cwd.startswith(home + os.sep):
        rel_path = os.path.relpath(cwd, home)
        current = home
        path = os.path.join(current, config_file_name)
        if os.path.isfile(path):
            config_files.append(path)

        if rel_path != ".":
            for part in rel_path.split(os.sep):
                current = os.path.join(current, part)
                path = os.path.join(current, config_file_name)
                if os.path.isfile(path):
                    config_files.append(path)
    else:
        path = os.path.join(cwd, config_file_name)
        if os.path.isfile(path):
            config_files.append(path)

    return config_files


def _merge_mcp_servers_config(config_files: list[str]) -> dict[str, dict[str, object]]:
    merged_servers: dict[str, dict[str, object]] = {}

    for config_file in config_files:
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "mcpServers" in data and isinstance(data["mcpServers"], dict):
                    merged_servers.update(data["mcpServers"])
        except Exception as e:
            zrb_print(
                f"Warning: Failed to load MCP config from {config_file}: {e}",
                plain=True,
            )

    return merged_servers


def _create_mcp_toolsets(
    merged_servers: dict[str, dict[str, object]],
) -> "list[AbstractToolset]":
    # lazy: heavy third-party
    from fastmcp.client.transports import StdioTransport

    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import MCPToolset

    toolsets: "list[AbstractToolset]" = []

    for server_name, config in merged_servers.items():
        try:
            if "command" in config:
                target = StdioTransport(
                    command=_expanded_text(config["command"], "'command'"),
                    args=_expanded_text_list(config.get("args", []), "'args'"),
                    env=_expanded_env(config.get("env", {})) or None,
                )
            elif "url" in config:
                target = _expanded_text(config["url"], "'url'")
            else:
                continue
            toolset: "AbstractToolset" = add_purpose_to_mcp_tools(
                MCPToolset(
                    target,
                    id=server_name,
                    max_retries=CFG.LLM_MCP_MAX_RETRIES,
                    process_tool_call=_truncating_process_tool_call,
                )
            )
            # Two servers exposing the same tool name abort the whole run.
            if (prefix := config.get("prefix")) is not None:
                if not isinstance(prefix, str) or not _PREFIX_PATTERN.fullmatch(prefix):
                    raise ValueError(
                        f"prefix must be 1-62 letters, digits, '_' or '-', got {prefix!r}"
                    )
                toolset = toolset.prefixed(prefix).filtered(
                    _create_tool_name_length_filter(server_name)
                )
            toolsets.append(toolset)
        except Exception as e:
            zrb_print(
                f"Warning: Failed to create MCP server '{server_name}': {e}", plain=True
            )

    return toolsets


def add_purpose_to_mcp_tools(toolset: "AbstractToolset") -> "AbstractToolset":
    """Wrap *toolset* so a tool call served by it can say what it is for.

    `agent.common.create_safe_wrapper` gives every tool zrb builds an optional
    ``purpose``, but an MCP server owns its schema: the model's line has nowhere
    to go, and a call that carries one anyway is refused by the server's own
    validation, spending a round. Two halves close it, and neither works alone —
    the schema (so the model may write the line) and the drop below (so the
    server never sees an argument it did not ask for).

    A server that declares ``purpose`` itself keeps its own: the schema is left
    alone and the value is forwarded, because that parameter is the server's
    meaning rather than the narrator's line.
    """
    # lazy: heavy third-party
    from dataclasses import replace

    from pydantic_ai.toolsets import WrapperToolset

    class PurposeToolset(WrapperToolset[None]):
        @property
        def id(self) -> str | None:
            # The server's own id: zrb names the toolset after its server, and a
            # wrapper that answers None would rename every MCP server to nothing.
            return self.wrapped.id

        async def get_tools(
            self, ctx: "RunContext[None]"
        ) -> "dict[str, ToolsetTool[None]]":
            tools = await super().get_tools(ctx)
            declared: "dict[str, ToolsetTool[None]]" = {}
            for name, tool in tools.items():
                schema = with_declared_purpose(
                    tool.tool_def.parameters_json_schema or {}
                )
                if schema is None:
                    declared[name] = tool
                    continue
                metadata = {
                    **(tool.tool_def.metadata or {}),
                    DECLARED_PURPOSE_KEY: True,
                }
                declared[name] = replace(
                    tool,
                    tool_def=replace(
                        tool.tool_def,
                        parameters_json_schema=schema,
                        metadata=metadata,
                    ),
                )
            return declared

        async def call_tool(
            self,
            name: str,
            tool_args: "dict[str, object]",
            ctx: "RunContext[None]",
            tool: "ToolsetTool[None]",
        ) -> "ToolResult":
            if (tool.tool_def.metadata or {}).get(DECLARED_PURPOSE_KEY):
                tool_args = {
                    key: value for key, value in tool_args.items() if key != "purpose"
                }
            return await super().call_tool(name, tool_args, ctx, tool)

    return cast("AbstractToolset", PurposeToolset(toolset))


def _expanded_text(value: object, field: str) -> str:
    """*value* with ``${VAR}`` references expanded; refuses anything but text."""
    expanded = _expand_env_vars(value)
    if not isinstance(expanded, str):
        raise ValueError(f"{field} must be text, got {expanded!r}")
    return expanded


def _expanded_text_list(value: object, field: str) -> list[str]:
    """A config list's entries, each expanded and each required to be text."""
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field} must be a list, got {value!r}")
    return [_expanded_text(entry, field) for entry in value]


def _expanded_env(value: object) -> dict[str, str]:
    """A config mapping's entries, each expanded and each required to be text."""
    if not isinstance(value, Mapping):
        raise ValueError(f"'env' must be an object, got {value!r}")
    return {str(key): _expanded_text(entry, "'env'") for key, entry in value.items()}


def _create_tool_name_length_filter(
    server_name: str,
) -> "Callable[[RunContext[object], ToolDefinition], bool]":
    """Drop a prefixed tool whose name grew past the provider limit, warning once.

    Skipping one tool beats a provider rejecting the whole request.
    """
    warned: set[str] = set()

    def is_short_enough(_ctx: "RunContext[object]", tool_def: "ToolDefinition") -> bool:
        if len(tool_def.name) <= _MAX_TOOL_NAME_LENGTH:
            return True
        if tool_def.name not in warned:
            warned.add(tool_def.name)
            zrb_print(
                f"Warning: Skipping MCP tool '{tool_def.name}' from '{server_name}': "
                f"prefixed name exceeds {_MAX_TOOL_NAME_LENGTH} characters",
                plain=True,
            )
        return False

    return is_short_enough


def cap_mcp_result(result: "ToolResult") -> "ToolResult":
    """Bound an MCP tool result's text to ``CFG.LLM_MAX_OUTPUT_CHARS``.

    An oversized result would overflow the rate limiter's per-minute budget and
    livelock the next request. Binary parts (e.g. images) pass through untouched.
    """
    capped, _ = _cap_against_budget(result, CFG.LLM_MAX_OUTPUT_CHARS)
    return capped


def frame_mcp_result(result: "ToolResult") -> "ToolResult":
    """Attach the "this is data, not instructions" note to a string/dict result,
    or to each item of a top-level list. Other parts pass through untouched.
    """
    if isinstance(result, str):
        return f"{result}\n\n[{UNTRUSTED_DATA_NOTE}]"
    if isinstance(result, dict):
        if "content_is" in result:
            return result
        return {**result, "content_is": UNTRUSTED_DATA_NOTE}
    if isinstance(result, list):
        return [frame_mcp_result(item) for item in result]
    return result


def _cap_against_budget(result: "ToolResult", budget: int) -> "tuple[ToolResult, int]":
    """Cap ``result`` against one ``budget`` shared by the whole structure;
    returns ``(capped, left)``."""
    if isinstance(result, str):
        capped, _ = truncate_text(result, max(budget, 0), keep="head")
        return capped, budget - len(capped)
    if isinstance(result, (list, tuple)):
        items: "list[ToolResult]" = []
        dropped = 0
        for item in result:
            if budget <= 0 and _is_cappable(item):
                # Counted once at the end: per-item markers could overflow too.
                dropped += 1
                continue
            # Non-text parts are never dropped: they cost no text budget.
            capped_item, budget = _cap_against_budget(item, budget)
            items.append(capped_item)
        if dropped:
            items.append(f"...[TRUNCATED {dropped} more parts]")
        return items, budget
    if isinstance(result, dict):
        try:
            as_json = json.dumps(result, ensure_ascii=False)
        except (TypeError, ValueError):
            return result, budget
        if len(as_json) <= budget:
            return result, budget - len(as_json)
        capped, _ = truncate_text(as_json, max(budget, 0), keep="head")
        return capped, budget - len(capped)
    # Binary/rich parts pass through uncharged.
    return result, budget


def _is_cappable(item: "ToolResult") -> bool:
    """True when ``item`` holds text this module would cap (and can drop)."""
    return isinstance(item, (str, list, tuple, dict))


async def _truncating_process_tool_call(
    _ctx: "RunContext[object]",
    call_tool: "CallToolFunc",
    name: str,
    tool_args: dict[str, object],
) -> "ToolResult":
    """pydantic-ai ``process_tool_call`` hook: cap and frame MCP results."""
    result = await call_tool(name, tool_args)
    return frame_mcp_result(cap_mcp_result(result))


def _expand_env_vars(value: object) -> object:
    """Recursively expand ``${VAR}`` / ``${VAR:-default}`` references in JSON-like values.

    Mirrors pydantic-ai's private ``pydantic_ai.mcp._expand_env_vars``.
    """
    if isinstance(value, str):

        def replace_match(match: re.Match[str]) -> str:
            var_name = match.group(1)
            has_default = match.group(2) is not None
            default_value = match.group(3) if has_default else None
            if var_name in os.environ:
                return os.environ[var_name]
            if has_default:
                return default_value or ""
            raise ValueError(f"Environment variable ${{{var_name}}} is not defined")

        return _ENV_VAR_PATTERN.sub(replace_match, value)
    if isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    return value
