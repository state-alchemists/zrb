"""LLM tool config: the env twin of ``tool_registry``."""

from __future__ import annotations

from zrb.config.env_field import EnvField, comma_join, comma_list


class LLMToolsMixin:
    def __init__(self):
        self.DEFAULT_LLM_TOOLS: str = ""
        super().__init__()

    LLM_TOOLS = EnvField(
        comma_list,
        serialize=comma_join,
        doc=(
            "Name allowlist for the tools zrb agents may call, the env twin of "
            "`tool_registry`. Empty means all built-in tools. Set it "
            "to a comma-separated list of registered tool names (e.g. "
            "'Shell,Read,Write,Grep') to expose only those. Finer edits live in "
            "zrb_init.py via `tool_registry.append_tool` / `remove_tool`."
        ),
    )
