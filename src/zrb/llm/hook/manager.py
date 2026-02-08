import asyncio
import json
import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

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

logger = logging.getLogger(__name__)


class HookManager:
    def __init__(
        self,
        auto_load: bool = True,
        scan_dirs: Optional[List[Union[str, Path]]] = None,
    ):
        self._hooks: Dict[HookEvent, List[HookCallable]] = defaultdict(list)
        self._global_hooks: List[HookCallable] = []
        self._executor: ThreadPoolHookExecutor = get_hook_executor()
        self._hook_configs: Dict[str, HookConfig] = {}  # name -> config for debugging
        self._hook_to_config: Dict[HookCallable, HookConfig] = (
            {}
        )  # hook -> config mapping
        if auto_load:
            self.scan(scan_dirs)

    def _evaluate_matchers(
        self, matchers: List[MatcherConfig], context: HookContext
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
        events: Optional[List[HookEvent]] = None,
        config: Optional[HookConfig] = None,
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
        session_id: Optional[str] = None,
        metadata: Dict[str, Any] = None,
        cwd: Optional[str] = None,
        transcript_path: Optional[str] = None,
        permission_mode: str = "default",
        **kwargs,
    ) -> List[HookExecutionResult]:
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

        results: List[HookExecutionResult] = []

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
        session_id: Optional[str] = None,
        metadata: Dict[str, Any] = None,
    ) -> List[HookResult]:
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
        results: List[HookResult] = []
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


hook_manager = HookManager(auto_load=CFG.HOOKS_ENABLED, scan_dirs=CFG.HOOKS_DIRS)
