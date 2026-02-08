import asyncio
import json
import logging
import os
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from zrb.config.config import CFG
from zrb.llm.hook.executor import (
    HookExecutionResult,
    ThreadPoolHookExecutor,
    get_hook_executor,
)
from zrb.llm.hook.interface import HookCallable, HookContext, HookResult
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

# Mapping from HookEvent to the field that Claude Code matchers apply to
CLAUDE_EVENT_MATCHER_FIELDS = {
    HookEvent.PRE_TOOL_USE: "tool_name",
    HookEvent.POST_TOOL_USE: "tool_name",
    HookEvent.POST_TOOL_USE_FAILURE: "tool_name",
    HookEvent.PERMISSION_REQUEST: "tool_name",  # Often matches tool name
    HookEvent.USER_PROMPT_SUBMIT: "prompt",
    HookEvent.SESSION_START: "source",
    HookEvent.NOTIFICATION: "message",
    HookEvent.SUBAGENT_START: "agent_type",  # Or agent_id
    HookEvent.SUBAGENT_STOP: "agent_type",
    HookEvent.TASK_COMPLETED: "task_id",
}

_IGNORE_DIRS = []


class HookManager:
    def __init__(
        self,
        auto_load: bool = True,
        search_dirs: list[str | Path] | None = None,
        max_depth: int = 1,
        ignore_dirs: list[str] | None = None,
    ):
        self._hooks: dict[HookEvent, list[HookCallable]] = defaultdict(list)
        self._global_hooks: list[HookCallable] = []
        self._executor: ThreadPoolHookExecutor = get_hook_executor()
        self._hook_configs: dict[str, HookConfig] = {}  # name -> config for debugging
        self._hook_to_config: dict[HookCallable, HookConfig] = (
            {}
        )  # hook -> config mapping
        self._max_depth = max_depth
        self._ignore_dirs = _IGNORE_DIRS if ignore_dirs is None else ignore_dirs
        if auto_load:
            self.scan(search_dirs)

    def _evaluate_matchers(
        self, matchers: list[MatcherConfig], context: HookContext
    ) -> bool:
        """
        Evaluate all matchers against the given context.
        Returns True if ALL matchers pass, False otherwise.

        Matchers can access fields in the context using dot notation.
        For example: "metadata.project" or "event_data.file_path"
        """
        if not matchers:
            return True  # No matchers means always match

        for matcher in matchers:
            # Get the value from context using dot notation
            value = self._get_field_value(context, matcher.field)

            # Apply case sensitivity if needed
            if not matcher.case_sensitive and isinstance(value, str):
                value = value.lower()
                matcher_value = (
                    matcher.value.lower()
                    if isinstance(matcher.value, str)
                    else matcher.value
                )
            else:
                matcher_value = matcher.value

            # Evaluate based on operator
            if matcher.operator == MatcherOperator.EQUALS:
                if value != matcher_value:
                    return False

            elif matcher.operator == MatcherOperator.NOT_EQUALS:
                if value == matcher_value:
                    return False

            elif matcher.operator == MatcherOperator.CONTAINS:
                if not isinstance(value, str) or not isinstance(matcher_value, str):
                    return False
                if matcher_value not in value:
                    return False

            elif matcher.operator == MatcherOperator.STARTS_WITH:
                if not isinstance(value, str) or not isinstance(matcher_value, str):
                    return False
                if not value.startswith(matcher_value):
                    return False

            elif matcher.operator == MatcherOperator.ENDS_WITH:
                if not isinstance(value, str) or not isinstance(matcher_value, str):
                    return False
                if not value.endswith(matcher_value):
                    return False

            elif matcher.operator == MatcherOperator.REGEX:
                import re

                if not isinstance(value, str) or not isinstance(matcher_value, str):
                    return False
                try:
                    if not re.search(matcher_value, value):
                        return False
                except re.error:
                    logger.warning(f"Invalid regex pattern in matcher: {matcher_value}")
                    return False

            elif matcher.operator == MatcherOperator.GLOB:
                import fnmatch

                if not isinstance(value, str) or not isinstance(matcher_value, str):
                    return False
                if not fnmatch.fnmatch(value, matcher_value):
                    return False

            else:
                logger.warning(f"Unknown matcher operator: {matcher.operator}")
                return False

        return True

    def _get_field_value(self, context: HookContext, field_path: str) -> Any:
        """
        Get a value from context using dot notation.
        Supports nested access like "metadata.project.name"
        """
        parts = field_path.split(".")
        current = context

        for part in parts:
            if hasattr(current, part):
                current = getattr(current, part)
            elif isinstance(current, dict) and part in current:
                current = current[part]
            else:
                # Try to access via getattr with default
                try:
                    current = getattr(current, part)
                except AttributeError:
                    # Return None if field doesn't exist
                    return None

        return current

    def register(
        self,
        hook: HookCallable,
        events: list[HookEvent] | None = None,
        config: HookConfig | None = None,
    ):
        """
        Register a hook.
        If events is None or empty, the hook is treated as a global hook (runs on all events).
        Otherwise, it is registered for the specific events.
        """
        if config:
            self._hook_to_config[hook] = config

        if not events:
            self._global_hooks.append(hook)
        else:
            for event in events:
                self._hooks[event].append(hook)

    async def execute_hooks(
        self,
        event: HookEvent,
        event_data: Any,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        cwd: str | None = None,
        transcript_path: str | None = None,
        permission_mode: str = "default",
        **kwargs,
    ) -> list[HookExecutionResult]:
        """
        Execute all hooks registered for the given event with thread safety.
        Returns a list of HookExecutionResult objects with Claude Code compatibility.
        """
        if metadata is None:
            metadata = {}

        # Create enhanced context with Claude Code fields
        context = HookContext(
            event=event,
            event_data=event_data,
            session_id=session_id,
            metadata=metadata,
            cwd=cwd or os.getcwd(),
            transcript_path=transcript_path,
            permission_mode=permission_mode,
            hook_event_name=event.value,
        )

        # Populate event-specific fields from kwargs
        for key, value in kwargs.items():
            if hasattr(context, key):
                setattr(context, key, value)

        results: list[HookExecutionResult] = []

        # Combine global hooks and event-specific hooks
        hooks_to_run = self._global_hooks + self._hooks[event]

        if not hooks_to_run:
            return results

        # Sort hooks by priority (higher priority first)
        # Create a default config for hooks without config (e.g., manually registered)
        default_config = HookConfig(
            name="default",
            events=[],
            type=HookType.COMMAND,
            config=CommandHookConfig(command=""),
            priority=0,
        )
        hooks_to_run = sorted(
            hooks_to_run,
            key=lambda h: self._hook_to_config.get(h, default_config).priority,
            reverse=True,  # Higher priority first
        )

        # Execute hooks with thread pool and timeout controls
        tasks = []
        for hook in hooks_to_run:
            # Get timeout from config if available
            timeout = None
            if hook in self._hook_to_config:
                config = self._hook_to_config[hook]
                timeout = config.timeout

            task = self._executor.execute_hook(hook, context, timeout=timeout)
            tasks.append(task)

        # Wait for all hooks to complete
        hook_results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(hook_results):
            if isinstance(result, Exception):
                logger.error(
                    f"Error executing hook {i} for event {event}: {result}",
                    exc_info=True,
                )
                results.append(
                    HookExecutionResult(success=False, error=str(result), exit_code=1)
                )
            else:
                results.append(result)

                # Check for blocking decisions (exit code 2)
                if result.blocked or result.exit_code == 2:
                    logger.info(
                        f"Hook blocked execution. Stopping further hooks for event {event}."
                    )
                    # Return only results up to this point
                    return results[: i + 1]

                # Check for continue=false
                if not result.continue_execution:
                    logger.info(
                        f"Hook requested stop of all processing for event {event}."
                    )
                    return results[: i + 1]

        return results

    async def execute_hooks_simple(
        self,
        event: HookEvent,
        event_data: Any,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[HookResult]:
        """
        Backward compatibility method that returns old HookResult format.
        """
        exec_results = await self.execute_hooks(
            event=event,
            event_data=event_data,
            session_id=session_id,
            metadata=metadata,
        )

        # Convert to old format
        results: list[HookResult] = []
        for exec_result in exec_results:
            # Start with data which contains all modifications
            modifications = exec_result.data.copy() if exec_result.data else {}

            # Override with Claude Code specific fields if they exist
            if exec_result.decision:
                modifications["decision"] = exec_result.decision
            if exec_result.reason:
                modifications["reason"] = exec_result.reason
            if exec_result.permission_decision:
                modifications["permissionDecision"] = exec_result.permission_decision
            if exec_result.permission_decision_reason:
                modifications["permissionDecisionReason"] = (
                    exec_result.permission_decision_reason
                )
            if exec_result.additional_context:
                modifications["additionalContext"] = exec_result.additional_context
            if exec_result.updated_input:
                modifications["updatedInput"] = exec_result.updated_input
            if exec_result.system_message:
                modifications["systemMessage"] = exec_result.system_message
            if not exec_result.continue_execution:
                modifications["continue"] = False
            if exec_result.suppress_output:
                modifications["suppressOutput"] = True
            if exec_result.hook_specific_output:
                modifications["hookSpecificOutput"] = exec_result.hook_specific_output

            result = HookResult(
                success=exec_result.success,
                output=exec_result.message or exec_result.error,
                data=exec_result.data,
                modifications=modifications,
                should_stop=exec_result.blocked or not exec_result.continue_execution,
            )
            results.append(result)

        return results

    def scan(self, search_dirs: list[str | Path] | None = None):
        """
        Scan for hooks in default locations and provided directories.
        """
        self._hooks = defaultdict(list)
        self._global_hooks = []
        target_search_dirs = search_dirs
        if target_search_dirs is None:
            target_search_dirs = self.get_search_directories()

        for search_dir in target_search_dirs:
            self._load_from_path(search_dir)

    def get_search_directories(self) -> list[str | Path]:
        search_dirs: list[str | Path] = []
        zrb_dir_name = f".{CFG.ROOT_GROUP_NAME}"

        # 0. Plugins (Default Plugin -> User Plugins)
        # Default Plugin
        default_plugin_path = (
            Path(os.path.dirname(__file__)).parent.parent / "llm_plugin"
        )
        if default_plugin_path.exists() and default_plugin_path.is_dir():
            hooks_path = default_plugin_path / "hooks"
            if hooks_path.exists() and hooks_path.is_dir():
                search_dirs.append(hooks_path)
            hooks_file = default_plugin_path / "hooks.json"
            if hooks_file.exists() and hooks_file.is_file():
                search_dirs.append(hooks_file)

        # User Plugins
        for plugin_path_str in CFG.LLM_PLUGIN_DIRS:
            plugin_path = Path(plugin_path_str)
            if plugin_path.exists() and plugin_path.is_dir():
                hooks_path = plugin_path / "hooks"
                if hooks_path.exists() and hooks_path.is_dir():
                    search_dirs.append(hooks_path)
                hooks_file = plugin_path / "hooks.json"
                if hooks_file.exists() and hooks_file.is_file():
                    search_dirs.append(hooks_file)

        # 1. User global config (~/.zrb/hooks.json and ~/.zrb/hooks/)
        try:
            home = Path.home()
            # Claude style
            global_claude_hooks_file = home / ".claude" / "hooks.json"
            if global_claude_hooks_file.exists() and global_claude_hooks_file.is_file():
                search_dirs.append(global_claude_hooks_file)

            global_claude_hooks_dir = home / ".claude" / "hooks"
            if global_claude_hooks_dir.exists() and global_claude_hooks_dir.is_dir():
                search_dirs.append(global_claude_hooks_dir)

            # Zrb style
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
                # Claude style
                local_claude_hooks_file = project_dir / ".claude" / "hooks.json"
                if (
                    local_claude_hooks_file.exists()
                    and local_claude_hooks_file.is_file()
                ):
                    search_dirs.append(local_claude_hooks_file)

                local_claude_hooks_dir = project_dir / ".claude" / "hooks"
                if local_claude_hooks_dir.exists() and local_claude_hooks_dir.is_dir():
                    search_dirs.append(local_claude_hooks_dir)

                # Zrb style
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

    def _load_from_path(self, path: str | Path):
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
        self, base_dir: Path, current_dir: Path, max_depth: int, current_depth: int
    ):
        """Recursively scan directories with explicit depth control."""
        if current_depth > max_depth:
            return

        try:
            # List directory contents
            for item in current_dir.iterdir():
                if item.is_dir():
                    # Skip ignored directories
                    if item.name in self._ignore_dirs or item.name.startswith("."):
                        continue
                    # Recursively scan subdirectory
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

    def _load_hooks_from_python(self, file_path: Path):
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

    def _load_file(self, file_path: Path):
        logger.debug(f"Loading hooks from {file_path}")
        try:
            with open(file_path, "r") as f:
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
                # Check if it looks like a Zrb hook (has 'events' and 'type')
                if "events" in data and "type" in data:
                    self._parse_and_register(data, str(file_path))
                else:
                    # Fallback or warning?
                    pass

        except Exception as e:
            logger.error(f"Failed to load hooks from {file_path}: {e}")

    def _parse_claude_format(self, data: dict, source: str):
        """
        Parse Claude Code nested format:
        {
          "hooks": {
            "EventName": [
              {
                "matcher": "regex",
                "hooks": [ ... ]
              }
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

                # Create matchers
                matchers = []
                # If pattern is present, create a REGEX matcher for the appropriate field
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
                    else:
                        # If no specific field, maybe matching general content?
                        # For now, if no field mapping, we might skip matching logic or match on 'event_data'
                        # But Claude docs imply specific fields.
                        # We'll default to 'event_data' str representation if not mapped
                        # matchers.append(MatcherConfig(field="event_data", operator=MatcherOperator.REGEX, value=pattern))
                        pass

                for hook_def in hooks_list:
                    # Claude hook def: {"type": "command", "command": "...", ...}
                    try:
                        # Convert to Zrb HookConfig
                        # Generate a unique name
                        hook_name = f"claude_{event.value}_{uuid.uuid4().hex[:8]}"

                        hook_type_str = hook_def.get("type", "command")
                        # Map Claude types to Zrb types
                        if hook_type_str == "command":
                            zrb_type = HookType.COMMAND
                            config = CommandHookConfig(
                                command=hook_def.get("command", ""),
                                shell=True,  # Claude defaults to shell
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
                            priority=0,  # Claude hooks execute in order, Zrb supports priority. We'll use 0.
                        )

                        # Register
                        hook_callable = self._hydrate_hook(hook_config)
                        self.register(hook_callable, hook_config.events, hook_config)
                        logger.debug(
                            f"Registered Claude hook '{hook_name}' for {event.value}"
                        )

                    except Exception as e:
                        logger.error(f"Error parsing Claude hook in {source}: {e}")

    def _parse_and_register(self, data: dict, source: str):
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

    def _hydrate_hook(self, config: HookConfig) -> HookCallable:
        """
        Convert HookConfig into a HookCallable using appropriate executor.
        Wraps the actual hook with matcher evaluation.
        """
        # Create the actual hook callable
        if config.type == HookType.COMMAND:
            inner_hook = self._create_command_hook(config.config)
        elif config.type == HookType.PROMPT:
            inner_hook = self._create_prompt_hook(config.config)
        elif config.type == HookType.AGENT:
            inner_hook = self._create_agent_hook(config.config)
        else:

            async def placeholder_hook(context: HookContext) -> HookResult:
                logger.warning(
                    f"Executing placeholder for hook '{config.name}' (Type: {config.type})."
                )
                return HookResult(success=True, output=f"Placeholder for {config.name}")

            inner_hook = placeholder_hook

        # Store config for debugging and timeout lookup
        self._hook_configs[config.name] = config

        # Create wrapper that evaluates matchers
        async def hook_with_matchers(context: HookContext) -> HookResult:
            # Evaluate matchers first
            if not self._evaluate_matchers(config.matchers, context):
                logger.debug(
                    f"Hook '{config.name}' skipped due to matcher evaluation failure"
                )
                # Return a neutral result (not an error, just didn't run)
                return HookResult(success=True, output="Skipped due to matchers")

            # Handle Async execution
            if config.is_async and config.type == HookType.COMMAND:
                logger.debug(f"Executing async hook '{config.name}'")
                # Fire and forget
                asyncio.create_task(inner_hook(context))
                return HookResult(success=True, output="Async execution started")

            # Execute the actual hook
            return await inner_hook(context)

        return hook_with_matchers

    def _create_command_hook(self, config: CommandHookConfig) -> HookCallable:
        async def command_hook(context: HookContext) -> HookResult:
            import subprocess

            # Prepare environment with Claude Code context variables
            env = os.environ.copy()

            # Inject Claude Code context variables for hook scripts
            env["CLAUDE_HOOK_EVENT"] = str(context.event.value)
            env["CLAUDE_HOOK_EVENT_NAME"] = context.hook_event_name or str(
                context.event.value
            )
            env["CLAUDE_CWD"] = context.cwd or ""
            env["CLAUDE_TRANSCRIPT_PATH"] = context.transcript_path or ""
            env["CLAUDE_PERMISSION_MODE"] = context.permission_mode

            # Phase 7: Environment Variables
            env["CLAUDE_PROJECT_DIR"] = (
                context.cwd or os.getcwd()
            )  # Best guess for project root
            env["CLAUDE_PLUGIN_ROOT"] = (
                ""  # TODO: Need to pass this context if available
            )
            env["CLAUDE_CODE_REMOTE"] = "false"  # Zrb is typically local for now
            if context.metadata.get("remote"):
                env["CLAUDE_CODE_REMOTE"] = "true"

            # Inject event-specific data as JSON
            import json as json_module

            try:
                # Try to serialize event_data, fall back to string representation
                if context.event_data is not None:
                    env["CLAUDE_EVENT_DATA"] = json_module.dumps(context.event_data)
                else:
                    env["CLAUDE_EVENT_DATA"] = "null"
            except (TypeError, ValueError):
                # If not JSON serializable, use string representation
                env["CLAUDE_EVENT_DATA"] = str(context.event_data)

            # Add context fields to environment
            for field in [
                "tool_name",
                "tool_input",
                "prompt",
                "message",
                "title",
                "notification_type",
                "agent_id",
                "teammate_name",
                "task_id",
            ]:
                value = getattr(context, field, None)
                if value is not None:
                    if isinstance(value, dict):
                        env[f"CLAUDE_{field.upper()}"] = json_module.dumps(value)
                    else:
                        env[f"CLAUDE_{field.upper()}"] = str(value)

            try:
                # Run command with timeout
                process = await asyncio.create_subprocess_shell(
                    config.command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=config.working_dir or context.cwd,
                    env=env,
                )
                stdout, stderr = await process.communicate()

                output = stdout.decode().strip()
                stderr_output = stderr.decode().strip()

                # Claude Code compatibility: exit code 2 means block, 0 means success
                # Other non-zero exit codes are errors
                exit_code = process.returncode

                if exit_code == 2:
                    # Blocking decision - parse output for reason
                    modifications = {}
                    reason = "Blocked by hook"

                    try:
                        data = json_module.loads(output)
                        if isinstance(data, dict):
                            # Claude Code format: {"decision": "block", "reason": "...", ...}
                            modifications = data
                            if "reason" in data:
                                reason = data["reason"]
                    except Exception:
                        # If not JSON, use output as reason
                        if output:
                            reason = output

                    # Merge provided modifications with blocking modifications
                    blocking_modifications = {
                        "decision": "block",
                        "reason": reason,
                        "exit_code": 2,
                    }
                    blocking_modifications.update(modifications)
                    return HookResult(
                        success=False,
                        output=output,  # Include output for logging/debugging
                        should_stop=True,
                        modifications=blocking_modifications,
                    )

                elif exit_code == 0:
                    # Success - parse output for modifications
                    modifications = {}
                    try:
                        data = json_module.loads(output)
                        if isinstance(data, dict):
                            modifications = data
                    except Exception:
                        # Not JSON, treat as plain output
                        pass

                    return HookResult(
                        success=True, output=output, modifications=modifications
                    )
                else:
                    # Error case
                    error_msg = f"Command failed with exit code {exit_code}"
                    if stderr_output:
                        error_msg += f": {stderr_output}"
                    elif output:
                        error_msg += f": {output}"

                    logger.error(f"Command hook failed: {error_msg}")
                    return HookResult(success=False, output=error_msg)

            except Exception as e:
                logger.error(f"Error executing command hook: {e}")
                return HookResult(success=False, output=str(e))

        return command_hook

    def _create_prompt_hook(self, config: PromptHookConfig) -> HookCallable:
        async def prompt_hook(context: HookContext) -> HookResult:
            """
            Execute a prompt hook using the LLM system.
            This runs an LLM with the given prompt template and returns the result.
            """
            try:
                # Import here to avoid circular imports
                from pydantic_ai import Agent
                from pydantic_ai.models.openai import OpenAIModel

                # Get LLM configuration
                model_name = config.model or CFG.LLM_MODEL
                if not model_name:
                    logger.error("No LLM model configured for prompt hook")
                    return HookResult(success=False, output="No LLM model configured")

                # Parse model name (format: provider:model)
                if ":" in model_name:
                    provider, model = model_name.split(":", 1)
                else:
                    provider = "openai"
                    model = model_name

                # Create model based on provider
                if provider == "openai":
                    llm_model = OpenAIModel(model)
                else:
                    # For other providers, we'd need to handle them
                    # For now, use OpenAI as default
                    logger.warning(
                        f"Provider {provider} not fully supported, using OpenAI"
                    )
                    llm_model = OpenAIModel(model)

                # Create agent with the prompt
                agent = Agent(
                    model=llm_model,
                    system_prompt=config.system_prompt or "",
                    deps_type=dict,
                )

                # Format user prompt template with context
                # Simple template substitution using context fields
                user_prompt = config.user_prompt_template
                for field_name in dir(context):
                    if not field_name.startswith("_"):
                        field_value = getattr(context, field_name)
                        if isinstance(field_value, (str, int, float, bool)):
                            placeholder = f"{{{{{field_name}}}}}"
                            if placeholder in user_prompt:
                                user_prompt = user_prompt.replace(
                                    placeholder, str(field_value)
                                )

                # Run the agent
                result = await agent.run(user_prompt, deps={})

                # Parse the result for modifications
                modifications = {}
                try:
                    # Try to parse as JSON if it looks like JSON
                    import json

                    output_text = str(result.output)
                    if output_text.strip().startswith(
                        "{"
                    ) and output_text.strip().endswith("}"):
                        parsed = json.loads(output_text)
                        if isinstance(parsed, dict):
                            modifications = parsed
                except Exception:
                    # Not JSON, use as plain output
                    pass

                return HookResult(
                    success=True, output=str(result.output), modifications=modifications
                )

            except Exception as e:
                logger.error(f"Error executing prompt hook: {e}", exc_info=True)
                return HookResult(success=False, output=str(e))

        return prompt_hook

    def _create_agent_hook(self, config: AgentHookConfig) -> HookCallable:
        async def agent_hook(context: HookContext) -> HookResult:
            """
            Execute an agent hook with tools.
            This creates an agent with the given system prompt and tools.
            """
            try:
                # Import here to avoid circular imports
                from pydantic_ai import Agent
                from pydantic_ai.models.openai import OpenAIModel

                # Get LLM configuration
                model_name = config.model or CFG.LLM_MODEL
                if not model_name:
                    logger.error("No LLM model configured for agent hook")
                    return HookResult(success=False, output="No LLM model configured")

                # Parse model name (format: provider:model)
                if ":" in model_name:
                    provider, model = model_name.split(":", 1)
                else:
                    provider = "openai"
                    model = model_name

                # Create model based on provider
                if provider == "openai":
                    llm_model = OpenAIModel(model)
                else:
                    # For other providers, we'd need to handle them
                    # For now, use OpenAI as default
                    logger.warning(
                        f"Provider {provider} not fully supported, using OpenAI"
                    )
                    llm_model = OpenAIModel(model)

                # Create agent with system prompt
                agent = Agent(
                    model=llm_model,
                    system_prompt=config.system_prompt,
                    deps_type=dict,
                )

                # TODO: Add tools from config.tools
                # For now, run without tools

                # Create a prompt from context
                # Use event_data or other context fields as input
                user_input = ""
                if context.event_data:
                    if isinstance(context.event_data, dict):
                        user_input = str(context.event_data)
                    else:
                        user_input = str(context.event_data)
                elif hasattr(context, "prompt") and context.prompt:
                    user_input = context.prompt
                else:
                    user_input = f"Hook event: {context.event.value}"

                # Run the agent
                result = await agent.run(user_input, deps={})

                # Parse the result for modifications
                modifications = {}
                try:
                    # Try to parse as JSON if it looks like JSON
                    import json

                    output_text = str(result.output)
                    if output_text.strip().startswith(
                        "{"
                    ) and output_text.strip().endswith("}"):
                        parsed = json.loads(output_text)
                        if isinstance(parsed, dict):
                            modifications = parsed
                except Exception:
                    # Not JSON, use as plain output
                    pass

                return HookResult(
                    success=True, output=str(result.output), modifications=modifications
                )

            except Exception as e:
                logger.error(f"Error executing agent hook: {e}", exc_info=True)
                return HookResult(success=False, output=str(e))

        return agent_hook


hook_manager = HookManager(auto_load=CFG.HOOKS_ENABLED, search_dirs=CFG.HOOKS_DIRS)
