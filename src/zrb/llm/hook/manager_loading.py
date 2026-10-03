"""Filesystem loading and config parsing for `HookManager`.

This mixin holds everything that walks directories, reads JSON/YAML, and
hydrates raw dicts into `HookConfig` objects. Splitting it out keeps the main
`HookManager` focused on registration, execution, and the type-specific hook
factories.
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zrb.llm.hook.hook_loader import get_plugin_root_for_path
from zrb.llm.hook.matcher import CLAUDE_EVENT_MATCHER_FIELDS
from zrb.llm.hook.schema import (
    AgentHookConfig,
    CommandHookConfig,
    HookConfig,
    MatcherConfig,
    PromptHookConfig,
)
from zrb.llm.hook.types import HookEvent, HookType, MatcherOperator
from zrb.util.asset_scanner import scan_files
from zrb.util.load import load_module_from_path

if TYPE_CHECKING:
    from zrb.llm.hook.interface import HookCallable

logger = logging.getLogger(__name__)


class HookManagerLoading:
    """Filesystem + format-parsing for HookManager."""

    # Host-class contract: state and methods owned by `HookManager`. Declared
    # here so static type checkers can verify accesses; the block does not run
    # at runtime.
    if TYPE_CHECKING:
        _max_depth: int
        _ignore_dirs: list[str]

        def _hydrate_hook(self, config: HookConfig) -> "HookCallable": ...

        def add_hook(
            self,
            hook: "HookCallable",
            events: list[HookEvent] | None = None,
            config: HookConfig | None = None,
        ) -> None: ...

    # --- Filesystem traversal --------------------------------------------

    def _load_from_path(self, path: str | Path) -> None:
        try:
            search_path = Path(path).resolve()
            if search_path.is_file():
                self._load_hook_file(search_path)
            else:
                scan_files(
                    search_path,
                    self._max_depth,
                    self._load_hook_file,
                    ignore_dirs=list(self._ignore_dirs),
                )
        except Exception as e:
            logger.debug(f"Failed to load hooks from {path}: {e}")

    def _load_hook_file(self, item: Path) -> None:
        if item.suffix in [".json", ".yaml", ".yml"]:
            self._load_file(item)
        elif item.name.endswith(".hook.py"):
            self._load_hooks_from_python(item)

    def _load_hooks_from_python(self, file_path: Path) -> None:
        try:
            module_name = f"zrb_hook_{uuid.uuid4().hex}"
            module = load_module_from_path(module_name, str(file_path))
            if not module:
                return

            if hasattr(module, "register") and callable(module.register):
                module.register(self)
            elif hasattr(module, "register_hooks") and callable(module.register_hooks):
                module.register_hooks(self)
        except Exception as e:
            logger.error(f"Failed to load python hooks from {file_path}: {e}")

    # --- JSON / YAML loading & format dispatch ---------------------------

    def _load_file(self, file_path: Path) -> None:
        logger.debug(f"Loading hooks from {file_path}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                if file_path.suffix == ".json":
                    data = json.load(f)
                else:
                    # lazy: heavy third-party -- yaml costs ~20 ms at startup,
                    # and only a project with a YAML hook file reads one
                    import yaml

                    data = yaml.safe_load(f)

            if (
                isinstance(data, dict)
                and "hooks" in data
                and isinstance(data["hooks"], dict)
            ):
                # Claude Code Nested Format
                self._parse_claude_format(data, str(file_path))
            elif isinstance(data, list):
                # Zrb Flat Format (List)
                for item in data:
                    self._parse_and_register(item, str(file_path))
            elif isinstance(data, dict):
                # Zrb Flat Format (Single Dict or unknown)
                if "events" in data and "type" in data:
                    self._parse_and_register(data, str(file_path))
                # else: silently ignore — dict without `events`+`type` is not a hook

        except Exception as e:
            logger.error(f"Failed to load hooks from {file_path}: {e}")

    def parse_claude_format(self, data: dict, source: str) -> None:
        """Public: parse a Claude-nested hook config and register its hooks.

        Used by external loaders (e.g. skill frontmatter) so they don't reach
        into the private `_parse_claude_format`.
        """
        self._parse_claude_format(data, source)

    def parse_and_register(self, data: dict, source: str) -> None:
        """Public: parse one flat (Zrb-format) hook entry and register it."""
        self._parse_and_register(data, source)

    def build_hook_configs(self, data: object, source: str) -> list[HookConfig]:
        """Public: parse hook declarations into `HookConfig`s, registering nothing.

        Accepts the shapes the file loader does: a Claude-nested mapping under
        `hooks`, a flat list of entries, or one flat entry. Nothing is
        registered, so the caller decides where the parsed hooks go — skill
        frontmatter hands the same configs to every manager (see
        `zrb.llm.hook.skill_frontmatter`).
        """
        if isinstance(data, dict):
            if isinstance(data.get("hooks"), dict):
                return self.build_claude_format_configs(data, source)
            if "events" in data and "type" in data:
                return self._build_flat_configs(data, source)
            return []
        if isinstance(data, list):
            return self._build_flat_configs(data, source)
        return []

    def build_claude_format_configs(self, data: dict, source: str) -> list[HookConfig]:
        """Public: the `HookConfig`s a Claude-nested hook block declares.

        Shape::

            {
              "hooks": {
                "EventName": [
                  {"matcher": "regex", "hooks": [ ... ]}
                ]
              }
            }

        An event zrb does not emit, or a hook entry that fails to parse, is
        logged and skipped — the same tolerance the registering path has.
        """
        configs: list[HookConfig] = []
        for event_name, matcher_groups in data.get("hooks", {}).items():
            try:
                event = HookEvent.from_claude_string(event_name)
            except ValueError:
                # Claude Code configs (e.g. peon-ping's settings.json) legitimately
                # register events zrb does not emit — SubagentStart/Stop, etc.
                # Skip them quietly, the same way Claude Code ignores hook events
                # it doesn't recognize. debug-level keeps this diagnosable without
                # spamming a warning on every load.
                logger.debug(
                    f"Skipping unsupported event in Claude config: {event_name}"
                )
                continue
            if not isinstance(matcher_groups, list):
                continue
            for group in matcher_groups:
                configs.extend(_build_claude_group_configs(event, group, source))
        return configs

    def _parse_claude_format(self, data: dict, source: str) -> None:
        """Parse a Claude-nested hook block and register its hooks."""
        for config in self.build_claude_format_configs(data, source):
            hook_callable = self._hydrate_hook(config)
            self.add_hook(hook_callable, config.events, config)
            logger.debug(f"Registered Claude hook '{config.name}' from {source}")

    def _build_flat_configs(self, data: object, source: str) -> list[HookConfig]:
        """Parse one flat entry or a list of them, logging and skipping a bad one."""
        items: list = data if isinstance(data, list) else [data]
        configs: list[HookConfig] = []
        for item in items:
            try:
                configs.append(self._create_hook_config(item, source))
            except Exception as e:
                logger.error(
                    f"Error registering hook from {source}: {e}", exc_info=True
                )
        return configs

    def _parse_and_register(self, data: dict, source: str) -> None:
        """Parse one flat entry and register it; a malformed one is logged."""
        for config in self._build_flat_configs(data, source):
            self.register_hook_config(config, source=source)

    def register_hook_config(
        self, config: "HookConfig", source: str = "python"
    ) -> "HookCallable | None":
        """Hydrate and register an already-built `HookConfig` — the same last
        step `_parse_and_register` takes after parsing JSON, exposed directly
        for hook factories (`add_hook_factory`) that build a `HookConfig` in
        Python rather than from a file. A no-op if `config.enabled` is False,
        matching the JSON-loading path.

        Returns the hydrated hook callable, or `None` when the config was
        disabled and nothing was registered. A caller that has to be able to
        take a registration back later — a re-scan replacing a source's hooks —
        needs the callable to hand to `remove_hook`.
        """
        if not config.enabled:
            return None
        hook_callable = self._hydrate_hook(config)
        self.add_hook(hook_callable, config.events, config)
        logger.info(f"Registered hook '{config.name}' from {source}")
        return hook_callable

    def _create_hook_config(self, data: dict, source: str | None = None) -> HookConfig:
        # Manual parsing because we are not using Pydantic BaseModel
        name = data["name"]
        events = [HookEvent(e) for e in data["events"]]
        hook_type = HookType(data["type"])

        raw_config = data["config"]
        default_timeout = 30
        config: Any
        if hook_type == HookType.COMMAND:
            config = CommandHookConfig(
                command=raw_config["command"],
                shell=raw_config.get("shell", True),
                working_dir=raw_config.get("working_dir"),
                plugin_root=(
                    get_plugin_root_for_path(source) if source is not None else None
                ),
            )
            default_timeout = 600
        elif hook_type == HookType.PROMPT:
            config = PromptHookConfig(
                user_prompt_template=raw_config["user_prompt_template"],
                system_prompt=raw_config.get("system_prompt"),
                model=raw_config.get("model"),
                temperature=raw_config.get("temperature", 0.0),
            )
            default_timeout = 30
        elif hook_type == HookType.AGENT:
            config = AgentHookConfig(
                system_prompt=raw_config["system_prompt"],
                tools=raw_config.get("tools"),
                model=raw_config.get("model"),
            )
            default_timeout = 60
        else:
            raise ValueError(f"Unknown hook type: {hook_type}")

        matchers = []
        for m in data.get("matchers", []):
            matchers.append(
                MatcherConfig(
                    field=m["field"],
                    operator=MatcherOperator(m["operator"]),
                    value=m["value"],
                    case_sensitive=m.get("case_sensitive", True),
                )
            )

        return HookConfig(
            name=name,
            events=events,
            type=hook_type,
            config=config,
            description=data.get("description"),
            matchers=matchers,
            is_async=data.get("async", False),
            enabled=data.get("enabled", True),
            timeout=data.get("timeout", default_timeout),
            env=data.get("env"),
            priority=data.get("priority", 0),
        )


def _build_claude_group_configs(
    event: HookEvent, group: dict, source: str
) -> list[HookConfig]:
    """The configs one `{matcher, hooks}` group of a Claude block declares."""
    matchers: list[MatcherConfig] = []
    pattern = group.get("matcher")
    if pattern:
        field = CLAUDE_EVENT_MATCHER_FIELDS.get(event)
        if field:
            matchers.append(
                MatcherConfig(field=field, operator=MatcherOperator.REGEX, value=pattern)
            )
    configs: list[HookConfig] = []
    for hook_def in group.get("hooks", []):
        try:
            config = _build_claude_hook_config(event, hook_def, matchers, source)
        except Exception as e:
            logger.error(f"Error parsing Claude hook in {source}: {e}")
            continue
        if config is not None:
            configs.append(config)
    return configs


def _build_claude_hook_config(
    event: HookEvent, hook_def: dict, matchers: list[MatcherConfig], source: str
) -> HookConfig | None:
    """The config one hook definition declares, or None for an unsupported type.

    `command` is the only type this format carries so far.
    """
    if hook_def.get("type", "command") != "command":
        return None
    return HookConfig(
        name=f"claude_{event.value}_{uuid.uuid4().hex[:8]}",
        events=[event],
        type=HookType.COMMAND,
        config=CommandHookConfig(
            command=hook_def.get("command", ""),
            shell=True,
            working_dir=None,
            plugin_root=get_plugin_root_for_path(source),
        ),
        matchers=matchers,
        is_async=hook_def.get("async", False),
        timeout=hook_def.get("timeout"),
        priority=0,
    )
