import asyncio
import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from zrb.config.config import CFG
from zrb.llm.hook._loader_mixin import HookLoaderMixin
from zrb.llm.hook.executor import (
    HookExecutionResult,
    ThreadPoolHookExecutor,
    get_hook_executor,
)
from zrb.llm.hook.interface import HookCallable, HookContext, HookResult
from zrb.llm.hook.matcher import evaluate_matchers
from zrb.llm.hook.schema import (
    AgentHookConfig,
    CommandHookConfig,
    HookConfig,
    PromptHookConfig,
)
from zrb.llm.hook.types import HookEvent, HookType

logger = logging.getLogger(__name__)

_IGNORE_DIRS: list[str] = []


class HookManager(HookLoaderMixin):
    def __init__(
        self,
        search_dirs: list[str | Path] | None = None,
        max_depth: int = 1,
        ignore_dirs: list[str] | None = None,
    ):
        # Lightweight: just assign properties, no heavy operations
        self._hooks: dict[HookEvent, list[HookCallable]] = defaultdict(list)
        self._global_hooks: list[HookCallable] = []
        self._executor: ThreadPoolHookExecutor = get_hook_executor()
        self._hook_configs: dict[str, HookConfig] = {}  # name -> config for debugging
        self._hook_to_config: dict[HookCallable, HookConfig] = (
            {}
        )  # hook -> config mapping
        self._hook_factories: list[Callable[[HookManager], None]] = []
        self._max_depth = max_depth
        self._ignore_dirs = _IGNORE_DIRS if ignore_dirs is None else ignore_dirs
        self._search_dirs: list[str | Path] | None = search_dirs
        self._loaded: bool = False  # Track if hooks have been loaded

    def _ensure_loaded(self):
        """Lazy load hooks on first access. No-op if already loaded."""
        if not self._loaded:
            self._scan_and_load()
            self._loaded = True

    def reload(self):
        """Force re-scan hooks. Use after CFG changes or hook file updates."""
        self._loaded = False
        self._hooks = defaultdict(list)
        self._global_hooks = []
        self._hook_configs = {}
        self._hook_to_config = {}
        # Re-run factories to re-register dynamic hooks
        for factory in self._hook_factories:
            factory(self)
        self._ensure_loaded()

    def _scan_and_load(self):
        """Internal: scan filesystem and load hooks without resetting existing ones."""
        target_search_dirs = self._search_dirs
        if target_search_dirs is None:
            target_search_dirs = self.get_search_directories()

        for search_dir in target_search_dirs:
            self._load_from_path(search_dir)

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
        # Lazy load hooks on first execution
        self._ensure_loaded()

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

        # Execute hooks sequentially to support blocking/continue logic
        for i, hook in enumerate(hooks_to_run):
            # Get timeout from config if available
            timeout = None
            if hook in self._hook_to_config:
                config = self._hook_to_config[hook]
                timeout = config.timeout

            try:
                result = await self._executor.execute_hook(
                    hook, context, timeout=timeout
                )
                results.append(result)
            except Exception as e:
                logger.error(
                    f"Error executing hook {i} for event {event}: {e}",
                    exc_info=True,
                )
                results.append(
                    HookExecutionResult(success=False, error=str(e), exit_code=1)
                )
                # Continue to next hook even if this one failed
                continue

            # Check for blocking decisions (exit code 2)
            if results[-1].blocked or results[-1].exit_code == 2:
                logger.info(
                    f"Hook blocked execution. Stopping further hooks for event {event}."
                )
                return results

            # Check for continue=false
            if not results[-1].continue_execution:
                logger.info(f"Hook requested stop of all processing for event {event}.")
                return results

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

    def add_hook_factory(self, factory: Callable[["HookManager"], None]):
        """Register a hook factory function.

        Factories are called during hook loading to dynamically register hooks.
        This allows hooks to be conditionally registered based on config or other factors.

        Args:
            factory: A function that takes HookManager and registers hooks
        """
        self._hook_factories.append(factory)

    def scan(self, search_dirs: list[str | Path] | None = None):
        """
        Scan for hooks in default locations and provided directories.
        This method can be called manually to add filesystem hooks.
        Does NOT clear manually registered hooks.
        """
        target_search_dirs = search_dirs
        if target_search_dirs is None:
            target_search_dirs = self.get_search_directories()

        # Run hook factories to register dynamic hooks
        for factory in self._hook_factories:
            factory(self)

        for search_dir in target_search_dirs:
            self._load_from_path(search_dir)

        self._loaded = True

    def get_search_directories(self) -> list[str | Path]:
        search_dirs: list[str | Path] = []
        zrb_dir_name = f".{CFG.ROOT_GROUP_NAME}"

        # 0. Plugins (Default Plugin -> User Plugins)
        # Default Plugin
        default_plugin_path = Path(__file__).parent.parent.parent / "llm_plugin"
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
            if not evaluate_matchers(config.matchers, context):
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


# Module-level singleton - lightweight, hooks loaded on first execute_hooks() call
hook_manager = HookManager()
