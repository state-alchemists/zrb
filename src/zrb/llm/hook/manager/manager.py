import asyncio
import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from zrb.config.config import CFG
from zrb.llm.hook.executor import (
    HookExecutionResult,
    ThreadPoolHookExecutor,
    get_hook_executor,
)
from zrb.llm.hook.hook_creators import (
    create_agent_hook,
    create_command_hook,
    create_prompt_hook,
)
from zrb.llm.hook.hook_loader import get_search_directories as _get_search_directories
from zrb.llm.hook.hook_loader import (
    parse_hook_config,
)
from zrb.llm.hook.interface import HookCallable, HookContext, HookResult
from zrb.llm.hook.manager.loader_mixin import HookLoaderMixin
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
        return _get_search_directories()

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
        return create_command_hook(config)

    def _create_prompt_hook(self, config: PromptHookConfig) -> HookCallable:
        return create_prompt_hook(config)

    def _create_agent_hook(self, config: AgentHookConfig) -> HookCallable:
        return create_agent_hook(config)


# Module-level singleton - lightweight, hooks loaded on first execute_hooks() call
hook_manager = HookManager()
