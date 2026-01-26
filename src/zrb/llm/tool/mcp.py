import json
import os
from typing import Any

from zrb.config.config import CFG
from zrb.context.any_context import zrb_print


def load_mcp_config(config_file_name: str | None = None) -> list[Any]:
    if config_file_name is None:
        config_file_name = CFG.MCP_CONFIG_FILE

    config_files = _get_config_files(config_file_name)
    if not config_files:
        return []

    merged_servers = _merge_mcp_servers_config(config_files)
    if not merged_servers:
        return []

    return _create_mcp_servers(merged_servers)


def _get_config_files(config_file_name: str) -> list[str]:
    home = os.path.abspath(os.path.expanduser("~"))
    cwd = os.path.abspath(os.getcwd())

    config_files: list[str] = []

    if cwd.startswith(home):
        # Traverse from home to cwd
        rel_path = os.path.relpath(cwd, home)
        current = home

        # Check home
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


def _create_mcp_servers(merged_servers: dict[str, Any]) -> list[Any]:
    from pydantic_ai.mcp import MCPServerSSE, MCPServerStdio, _expand_env_vars

    servers: list[Any] = []

    for server_name, config in merged_servers.items():
        try:
            if "command" in config:
                # Stdio
                command = _expand_env_vars(config["command"])
                args = [_expand_env_vars(arg) for arg in config.get("args", [])]
                env = {
                    k: _expand_env_vars(v) for k, v in config.get("env", {}).items()
                } or None

                servers.append(MCPServerStdio(command=command, args=args, env=env))
            elif "url" in config:
                # SSE
                url = _expand_env_vars(config["url"])
                servers.append(MCPServerSSE(url=url))
        except Exception as e:
            zrb_print(
                f"Warning: Failed to create MCP server '{server_name}': {e}", plain=True
            )

    return servers
