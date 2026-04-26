"""Filesystem loading and config parsing for `HookManager`.

This mixin holds everything that walks directories, reads JSON/YAML, and
hydrates raw dicts into `HookConfig` objects. Splitting it out keeps the main
`HookManager` focused on registration, execution, and the type-specific hook
factories.

The mixin assumes the host class provides:
- `self._max_depth: int`, `self._ignore_dirs: list[str]` (set in __init__)
- `self._hydrate_hook(config) -> HookCallable`
- `self.register(hook, events, config) -> None`
- `self._scan_and_load()` is implemented here and used by the host class.
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

import yaml

from zrb.llm.hook.matcher import CLAUDE_EVENT_MATCHER_FIELDS
from zrb.llm.hook.schema import (
    AgentHookConfig,
    CommandHookConfig,
    HookConfig,
    MatcherConfig,
    PromptHookConfig,
)
from zrb.llm.hook.types import HookEvent, HookType, MatcherOperator
from zrb.util.load import load_module_from_path

logger = logging.getLogger(__name__)


class HookLoaderMixin:
    """Filesystem + format-parsing for HookManager."""

    # --- Filesystem traversal --------------------------------------------

    def _load_from_path(self, path: str | Path) -> None:
        try:
            search_path = Path(path).resolve()
            if search_path.is_file():
                if search_path.suffix in [".json", ".yaml", ".yml"]:
                    self._load_file(search_path)
                elif search_path.name.endswith(".hook.py"):
                    self._load_hooks_from_python(search_path)
            else:
                self._scan_dir_recursive(search_path, search_path, self._max_depth, 0)
        except Exception:
            pass

    def _scan_dir_recursive(
        self,
        base_dir: Path,
        current_dir: Path,
        max_depth: int,
        current_depth: int,
    ) -> None:
        """Recursively scan directories with explicit depth control."""
        if current_depth > max_depth:
            return

        try:
            for item in current_dir.iterdir():
                if item.is_dir():
                    if item.name in self._ignore_dirs or item.name.startswith("."):
                        continue
                    self._scan_dir_recursive(
                        base_dir, item, max_depth, current_depth + 1
                    )
                elif item.is_file():
                    if item.suffix in [".json", ".yaml", ".yml"]:
                        self._load_file(item)
                    elif item.name.endswith(".hook.py"):
                        self._load_hooks_from_python(item)
        except (PermissionError, OSError):
            # Skip directories we can't access
            pass

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

    def _parse_claude_format(self, data: dict, source: str) -> None:
        """Parse Claude Code's nested hook format.

        Shape::

            {
              "hooks": {
                "EventName": [
                  {"matcher": "regex", "hooks": [ ... ]}
                ]
              }
            }
        """
        hooks_map = data.get("hooks", {})
        for event_name, matcher_groups in hooks_map.items():
            try:
                event = HookEvent.from_claude_string(event_name)
            except ValueError:
                logger.warning(f"Unknown event in Claude config: {event_name}")
                continue

            if not isinstance(matcher_groups, list):
                continue

            for group in matcher_groups:
                pattern = group.get("matcher")
                hooks_list = group.get("hooks", [])

                matchers: list[MatcherConfig] = []
                if pattern:
                    field = CLAUDE_EVENT_MATCHER_FIELDS.get(event)
                    if field:
                        matchers.append(
                            MatcherConfig(
                                field=field,
                                operator=MatcherOperator.REGEX,
                                value=pattern,
                            )
                        )

                for hook_def in hooks_list:
                    try:
                        hook_name = f"claude_{event.value}_{uuid.uuid4().hex[:8]}"

                        hook_type_str = hook_def.get("type", "command")
                        if hook_type_str == "command":
                            zrb_type = HookType.COMMAND
                            config = CommandHookConfig(
                                command=hook_def.get("command", ""),
                                shell=True,
                                working_dir=None,
                            )
                        else:
                            # Unsupported type in this pass
                            continue

                        hook_config = HookConfig(
                            name=hook_name,
                            events=[event],
                            type=zrb_type,
                            config=config,
                            matchers=matchers,
                            is_async=hook_def.get("async", False),
                            timeout=hook_def.get("timeout"),
                            priority=0,
                        )

                        hook_callable = self._hydrate_hook(hook_config)
                        self.register(hook_callable, hook_config.events, hook_config)
                        logger.debug(
                            f"Registered Claude hook '{hook_name}' for {event.value}"
                        )

                    except Exception as e:
                        logger.error(f"Error parsing Claude hook in {source}: {e}")

    def _parse_and_register(self, data: dict, source: str) -> None:
        try:
            config = self._create_hook_config(data)
            if not config.enabled:
                return

            hook_callable = self._hydrate_hook(config)
            self.register(hook_callable, config.events, config)
            logger.info(f"Registered hook '{config.name}' from {source}")
        except Exception as e:
            logger.error(f"Error registering hook from {source}: {e}", exc_info=True)

    def _create_hook_config(self, data: dict) -> HookConfig:
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
