import asyncio
import json
import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from zrb.config.config import CFG
from zrb.llm.hook.interface import HookCallable, HookContext, HookResult
from zrb.llm.hook.schema import (
    AgentHookConfig,
    CommandHookConfig,
    HookConfig,
    MatcherConfig,
    PromptHookConfig,
)
from zrb.llm.hook.types import HookEvent, HookType, MatcherOperator

logger = logging.getLogger(__name__)


class HookManager:
    def __init__(
        self,
        auto_load: bool = True,
        scan_dirs: Optional[List[Union[str, Path]]] = None,
    ):
        self._hooks: Dict[HookEvent, List[HookCallable]] = defaultdict(list)
        self._global_hooks: List[HookCallable] = []
        if auto_load:
            self.scan(scan_dirs)

    def register(self, hook: HookCallable, events: Optional[List[HookEvent]] = None):
        """
        Register a hook.
        If events is None or empty, the hook is treated as a global hook (runs on all events).
        Otherwise, it is registered for the specific events.
        """
        if not events:
            self._global_hooks.append(hook)
        else:
            for event in events:
                self._hooks[event].append(hook)

    async def execute_hooks(
        self,
        event: HookEvent,
        event_data: Any,
        session_id: Optional[str] = None,
        metadata: Dict[str, Any] = None,
    ) -> List[HookResult]:
        """
        Execute all hooks registered for the given event.
        Returns a list of HookResult objects.
        """
        if metadata is None:
            metadata = {}

        context = HookContext(
            event=event,
            event_data=event_data,
            session_id=session_id,
            metadata=metadata,
        )

        results: List[HookResult] = []

        # Combine global hooks and event-specific hooks
        hooks_to_run = self._global_hooks + self._hooks[event]

        if not hooks_to_run:
            return results

        # Execute hooks sequentially for now
        for hook in hooks_to_run:
            try:
                result = await hook(context)
                results.append(result)

                if result.should_stop:
                    logger.info(
                        f"Hook {hook} requested stop. "
                        f"Stopping execution of further hooks for event {event}."
                    )
                    break

            except Exception as e:
                logger.error(
                    f"Error executing hook {hook} for event {event}: {e}", exc_info=True
                )
                results.append(HookResult(success=False, output=str(e)))

        return results

    def scan(self, search_dirs: Optional[List[Union[str, Path]]] = None):
        """
        Scan for hooks in default locations and provided directories.
        """
        target_search_dirs = search_dirs
        if target_search_dirs is None:
            target_search_dirs = self.get_search_directories()

        for search_dir in target_search_dirs:
            self._load_from_path(search_dir)

    def get_search_directories(self) -> List[Union[str, Path]]:
        search_dirs: List[Union[str, Path]] = []
        zrb_dir_name = f".{CFG.ROOT_GROUP_NAME}"

        # 1. User global config (~/.zrb/hooks.json and ~/.zrb/hooks/)
        try:
            home = Path.home()
            global_zrb_hooks_file = home / zrb_dir_name / "hooks.json"
            if global_zrb_hooks_file.exists() and global_zrb_hooks_file.is_file():
                search_dirs.append(global_zrb_hooks_file)

            global_zrb_hooks_dir = home / zrb_dir_name / "hooks"
            if global_zrb_hooks_dir.exists() and global_zrb_hooks_dir.is_dir():
                search_dirs.append(global_zrb_hooks_dir)
        except Exception:
            pass

        # 2. Project directories (.zrb/hooks.json and .zrb/hooks/)
        try:
            cwd = Path.cwd()
            project_dirs = list(cwd.parents)[::-1] + [cwd]
            for project_dir in project_dirs:
                local_zrb_hooks_file = project_dir / zrb_dir_name / "hooks.json"
                if local_zrb_hooks_file.exists() and local_zrb_hooks_file.is_file():
                    search_dirs.append(local_zrb_hooks_file)

                local_zrb_hooks_dir = project_dir / zrb_dir_name / "hooks"
                if local_zrb_hooks_dir.exists() and local_zrb_hooks_dir.is_dir():
                    search_dirs.append(local_zrb_hooks_dir)
        except Exception:
            pass

        # 3. Custom directories from CFG
        for d in CFG.HOOKS_DIRS:
            search_dirs.append(Path(d))

        return search_dirs

    def _load_from_path(self, path: Union[str, Path]):
        path = Path(path)
        if not path.exists():
            return

        if path.is_file():
            if path.suffix in [".json", ".yaml", ".yml"]:
                self._load_file(path)
        elif path.is_dir():
            for root, _, files in os.walk(path):
                for file in files:
                    file_path = Path(root) / file
                    if file_path.suffix in [".json", ".yaml", ".yml"]:
                        self._load_file(file_path)

    def _load_file(self, file_path: Path):
        logger.debug(f"Loading hooks from {file_path}")
        try:
            with open(file_path, "r") as f:
                if file_path.suffix == ".json":
                    data = json.load(f)
                else:
                    data = yaml.safe_load(f)

            if isinstance(data, list):
                for item in data:
                    self._parse_and_register(item, str(file_path))
            elif isinstance(data, dict):
                self._parse_and_register(data, str(file_path))

        except Exception as e:
            logger.error(f"Failed to load hooks from {file_path}: {e}")

    def _parse_and_register(self, data: dict, source: str):
        try:
            config = self._create_hook_config(data)
            if not config.enabled:
                return

            hook_callable = self._hydrate_hook(config)
            self.register(hook_callable, config.events)
            logger.info(f"Registered hook '{config.name}' from {source}")
        except Exception as e:
            logger.error(f"Error registering hook from {source}: {e}", exc_info=True)

    def _create_hook_config(self, data: dict) -> HookConfig:
        # Manual parsing because we are not using Pydantic BaseModel
        name = data["name"]
        events = [HookEvent(e) for e in data["events"]]
        hook_type = HookType(data["type"])

        raw_config = data["config"]
        if hook_type == HookType.COMMAND:
            config = CommandHookConfig(
                command=raw_config["command"],
                shell=raw_config.get("shell", True),
                working_dir=raw_config.get("working_dir"),
            )
        elif hook_type == HookType.PROMPT:
            config = PromptHookConfig(
                user_prompt_template=raw_config["user_prompt_template"],
                system_prompt=raw_config.get("system_prompt"),
                model=raw_config.get("model"),
                temperature=raw_config.get("temperature", 0.0),
            )
        elif hook_type == HookType.AGENT:
            config = AgentHookConfig(
                system_prompt=raw_config["system_prompt"],
                tools=raw_config.get("tools"),
                model=raw_config.get("model"),
            )
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
            timeout=data.get("timeout"),
            env=data.get("env"),
            priority=data.get("priority", 0),
        )

    def _hydrate_hook(self, config: HookConfig) -> HookCallable:
        """
        Convert HookConfig into a HookCallable using appropriate executor.
        """
        if config.type == HookType.COMMAND:
            return self._create_command_hook(config.config)
        if config.type == HookType.PROMPT:
            return self._create_prompt_hook(config.config)
        if config.type == HookType.AGENT:
            return self._create_agent_hook(config.config)

        async def placeholder_hook(context: HookContext) -> HookResult:
            logger.warning(
                f"Executing placeholder for hook '{config.name}' (Type: {config.type})."
            )
            return HookResult(success=True, output=f"Placeholder for {config.name}")

        return placeholder_hook

    def _create_command_hook(self, config: CommandHookConfig) -> HookCallable:
        async def command_hook(context: HookContext) -> HookResult:
            import subprocess

            # Prepare environment
            env = os.environ.copy()
            # In real implementation we might inject more context into env or stdin
            # For now, let's keep it simple: run command.
            try:
                # We use asyncio to run command if we want it non-blocking
                process = await asyncio.create_subprocess_shell(
                    config.command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=config.working_dir,
                    env=env,
                )
                stdout, stderr = await process.communicate()

                success = process.returncode == 0
                output = stdout.decode().strip()
                if not success:
                    logger.error(f"Command hook failed: {stderr.decode()}")

                # Attempt to parse output as JSON for modifications
                modifications = {}
                try:
                    data = json.loads(output)
                    if isinstance(data, dict) and "modifications" in data:
                        modifications = data["modifications"]
                except Exception:
                    pass

                return HookResult(
                    success=success, output=output, modifications=modifications
                )
            except Exception as e:
                logger.error(f"Error executing command hook: {e}")
                return HookResult(success=False, output=str(e))

        return command_hook

    def _create_prompt_hook(self, config: PromptHookConfig) -> HookCallable:
        async def prompt_hook(context: HookContext) -> HookResult:
            # We need to run an LLM task here.
            # This is complex because it might cause recursion if not careful.
            # For now, let's implement a simplified version using LLMTask logic
            from zrb.context.any_context import AnyContext
            from zrb.llm.task.llm_task import LLMTask

            # Create a temporary task to run the prompt
            task_name = f"hook-prompt-{id(context)}"

            # Simple context for the hook
            # In a real app, we should pass a better context
            # But LLMTask needs a context to run.
            # We'll use a dummy context for now if we don't have one.
            # Actually, we should probably have context in HookContext.

            # For Phase 1/2, let's just log and return.
            # Implementing full LLM call here requires careful context management.
            logger.info(f"Prompt hook triggered: {config.user_prompt_template}")
            return HookResult(success=True, output="Prompt hook executed (simulated)")

        return prompt_hook

    def _create_agent_hook(self, config: AgentHookConfig) -> HookCallable:
        async def agent_hook(context: HookContext) -> HookResult:
            logger.info(f"Agent hook triggered: {config.system_prompt}")
            return HookResult(success=True, output="Agent hook executed (simulated)")

        return agent_hook


hook_manager = HookManager(auto_load=CFG.HOOKS_ENABLED, scan_dirs=CFG.HOOKS_DIRS)
