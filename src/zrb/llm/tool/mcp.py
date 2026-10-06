import json
import os
import re
from typing import Any

from zrb.config.config import CFG
from zrb.context.any_context import zrb_print
from zrb.llm.tool_call.untrusted_data import UNTRUSTED_DATA_NOTE
from zrb.util.truncate import truncate_text

_ENV_VAR_PATTERN = re.compile(r"\$\{([^}:]+)(:-([^}]*))?\}")


def load_mcp_config(config_file_name: str | None = None) -> list[Any]:
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
        # Traverse from home down to cwd
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
        # Only check current directory
        path = os.path.join(cwd, config_file_name)
        if os.path.isfile(path):
            config_files.append(path)

    return config_files


def _merge_mcp_servers_config(config_files: list[str]) -> dict[str, Any]:
    merged_servers: dict[str, Any] = {}

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


def _create_mcp_toolsets(merged_servers: dict[str, Any]) -> list[Any]:
    # lazy: heavy third-party
    from fastmcp.client.transports import StdioTransport

    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import MCPToolset

    toolsets: list[Any] = []

    for server_name, config in merged_servers.items():
        try:
            if "command" in config:
                command = _expand_env_vars(config["command"])
                args = [_expand_env_vars(arg) for arg in config.get("args", [])]
                env = {
                    k: _expand_env_vars(v) for k, v in config.get("env", {}).items()
                } or None
                transport = StdioTransport(command=command, args=args, env=env)
                toolsets.append(
                    MCPToolset(
                        transport,
                        id=server_name,
                        max_retries=CFG.LLM_MCP_MAX_RETRIES,
                        process_tool_call=_truncating_process_tool_call,
                    )
                )
            elif "url" in config:
                url = _expand_env_vars(config["url"])
                toolsets.append(
                    MCPToolset(
                        url,
                        id=server_name,
                        max_retries=CFG.LLM_MCP_MAX_RETRIES,
                        process_tool_call=_truncating_process_tool_call,
                    )
                )
        except Exception as e:
            zrb_print(
                f"Warning: Failed to create MCP server '{server_name}': {e}", plain=True
            )

    return toolsets


def cap_mcp_result(result: Any) -> Any:
    """Bound an MCP tool result's text to ``CFG.LLM_MAX_OUTPUT_CHARS``.

    An oversized result would overflow the rate limiter's per-minute budget and
    livelock the next request. Binary parts (e.g. images) pass through untouched.
    """
    capped, _ = _cap_against_budget(result, CFG.LLM_MAX_OUTPUT_CHARS)
    return capped


def frame_mcp_result(result: Any) -> Any:
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


def _cap_against_budget(result: Any, budget: int) -> tuple[Any, int]:
    """Cap ``result`` against one ``budget`` shared by the whole structure;
    returns ``(capped, left)``."""
    if isinstance(result, str):
        capped, _ = truncate_text(result, max(budget, 0), keep="head")
        return capped, budget - len(capped)
    if isinstance(result, (list, tuple)):
        items: list[Any] = []
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


def _is_cappable(item: Any) -> bool:
    """True when ``item`` holds text this module would cap (and can drop)."""
    return isinstance(item, (str, list, tuple, dict))


async def _truncating_process_tool_call(
    _ctx: Any, call_tool: Any, name: str, tool_args
):
    """pydantic-ai ``process_tool_call`` hook: cap and frame MCP results."""
    result = await call_tool(name, tool_args)
    return frame_mcp_result(cap_mcp_result(result))


def _expand_env_vars(value: Any) -> Any:
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
