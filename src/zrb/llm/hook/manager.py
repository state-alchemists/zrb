"""`HookManager` — Claude-Code-compatible lifecycle hooks.

Owns hook registration, matcher evaluation, and execution. The filesystem
loading + JSON/YAML parsing lives in the sibling `manager_loading.py`; the
type-specific factories (command/prompt/agent) live in `zrb.llm.hook.creator`;
matcher operator semantics live in `zrb.llm.hook.matcher`.

For the public hook authoring guide (formats, events, examples), see:
  docs/advanced-topics/hooks.md
"""

import asyncio
import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, cast

from zrb.config.config import CFG
from zrb.llm.hook.creator import (
    create_agent_hook,
    create_command_hook,
    create_prompt_hook,
)
from zrb.llm.hook.executor import (
    HookExecutionResult,
    ThreadPoolHookExecutor,
    get_hook_executor,
)
from zrb.llm.hook.hook_loader import get_search_directories as _get_search_directories
from zrb.llm.hook.interface import HookCallable, HookContext, HookResult
from zrb.llm.hook.manager_loading import HookManagerLoading
from zrb.llm.hook.matcher import evaluate_matchers
from zrb.llm.hook.schema import (
    AgentHookConfig,
    CommandHookConfig,
    HookConfig,
    PromptHookConfig,
)
from zrb.llm.hook.types import BLOCKING_EVENTS, HookEvent, HookType

logger = logging.getLogger(__name__)

_IGNORE_DIRS: list[str] = []

# Bound fire-and-forget command hooks. A high-frequency event must not spawn an
# unbounded pile of subprocesses: that exhausted file descriptors ([Errno 24])
# and, when a serialized external tool (e.g. peon-ping) backed up, produced a
# timeout storm. The semaphore caps concurrent subprocesses; the pending ceiling
# sheds load by dropping new hooks once the backlog is full.
_MAX_CONCURRENT_BG_HOOKS = 4
_MAX_PENDING_BG_HOOKS = 64


class HookManager(HookManagerLoading):
    def __init__(
        self,
        search_dirs: list[str | Path] | None = None,
        max_depth: int = 1,
        ignore_dirs: list[str] | None = None,
    ):
        # Lightweight: just assign properties, no heavy operations
        """Discover and run lifecycle hooks.

        Args:
            search_dirs: Directories to scan for hook definitions. Defaults to
                the standard project and user locations.
            max_depth: How many directory levels below each search directory to
                descend.
            ignore_dirs: Directory names skipped while scanning, such as
                `node_modules`.
        """
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
        self._loaded: bool = False
        # Strong refs to fire-and-forget async hook tasks so the event loop
        # doesn't GC them mid-run (asyncio only keeps weak references).
        self._background_tasks: set[asyncio.Task] = set()
        # Bounds concurrent fire-and-forget subprocesses. Created lazily inside
        # the running loop (see _run_background_hook).
        self._bg_semaphore: asyncio.Semaphore | None = None

    @property
    def search_dirs(self) -> list[str | Path] | None:
        """Directories scanned for hook files; ``None`` means "ask the config".

        Assigning invalidates the load, so the next access rescans — which is
        how a caller points an already-constructed manager somewhere else (an
        empty list being the way to say "discover nothing").
        """
        return self._search_dirs

    @search_dirs.setter
    def search_dirs(self, value: list[str | Path] | None) -> None:
        self._search_dirs = value
        self._loaded = False

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
        # Global kill-switch (ZRB_HOOKS_ENABLED). When off, no hook fires and the
        # filesystem is never scanned — execute_hooks_simple delegates here, so
        # this one guard disables every firing path.
        if not CFG.HOOKS_ENABLED:
            return []

        self._ensure_loaded()

        if metadata is None:
            metadata = {}

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

        for key, value in kwargs.items():
            if hasattr(context, key):
                setattr(context, key, value)

        results: list[HookExecutionResult] = []

        hooks_to_run = self._global_hooks + self._hooks[event]

        if not hooks_to_run:
            return results

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

        # Sequential, not concurrent: a hook may block or stop the chain.
        for i, hook in enumerate(hooks_to_run):
            config = self._hook_to_config.get(hook)
            timeout = config.timeout if config else None

            # Async command hooks are fire-and-forget: spawn them on the current
            # (persistent) event loop and DON'T await. Awaiting them through the
            # thread executor would block here until the hook's subprocess — and
            # any child it forks, e.g. peon-ping's audio player — exits or the
            # timeout fires, defeating the whole point of `async` and stalling
            # the agent on every event (a per-output-chunk Notification hook
            # alone would add a multi-second wait per chunk). They cannot block
            # or contribute additionalContext, so omitting their result is
            # correct.
            if (
                config is not None
                and config.is_async
                and config.type == (HookType.COMMAND)
            ):
                if self._spawn_background_hook(hook, context):
                    continue
                # No running loop (rare sync caller) — fall through to the
                # executor so the hook still runs, just synchronously.

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
                continue

            # Check for blocking decisions (exit code 2). A block only halts the
            # chain for events that can actually be blocked; for any other event
            # the block is a no-op signal, so we keep running the remaining hooks
            # (Claude-compatible — exit 2 is meaningful only where the lifecycle
            # can be stopped).
            if results[-1].blocked or results[-1].exit_code == 2:
                if event in BLOCKING_EVENTS:
                    logger.info(
                        f"Hook blocked execution. Stopping further hooks for event {event}."
                    )
                    return results
                logger.debug(
                    f"Hook returned a block for non-blocking event {event}; "
                    "ignoring block and continuing remaining hooks."
                )

            # Check for continue=false (an explicit "stop all processing" request,
            # honored for every event regardless of whether it can be blocked).
            if not results[-1].continue_execution:
                logger.info(f"Hook requested stop of all processing for event {event}.")
                return results

        return results

    def _spawn_background_hook(self, hook: HookCallable, context: HookContext) -> bool:
        """Fire an async command hook without awaiting it.

        Returns False when there is no running loop (a rare synchronous caller),
        signalling the caller to run the hook through the executor instead. When
        the backlog is already at its ceiling the hook is dropped (the event is
        advisory — a sound/notification — so shedding is safe) and True is still
        returned so the caller does not also run it synchronously.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return False
        if len(self._background_tasks) >= _MAX_PENDING_BG_HOOKS:
            logger.debug(
                "Dropping background hook; %d already pending",
                len(self._background_tasks),
            )
            return True
        task = loop.create_task(self._run_background_hook(hook, context))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return True

    @property
    def has_pending_background_hooks(self) -> bool:
        """True while any fire-and-forget hook task is still running."""
        return any(not task.done() for task in self._background_tasks)

    async def shutdown(
        self, grace_seconds: float = 2.0, *, drain: bool = False
    ) -> None:
        """Cancel in-flight fire-and-forget hooks and wait for them to settle.

        Async ("fire-and-forget") hooks run detached, and their subprocesses run
        in their own session/process group — so the terminal's Ctrl+C SIGINT does
        not reach them. Without this, a slow async hook (an audio notifier, say)
        outlives the session that spawned it. Cancelling the task makes the
        command hook's own cancellation handler kill its process tree.

        Cancel up front rather than granting a grace period first: exit must stay
        snappy, and a detached hook still running at teardown is exactly what
        this exists to stop. Async hooks are fire-and-forget by construction, so
        one dispatched at SESSION_END has no completion guarantee to break.

        ``drain=True`` inverts that first step only: pending hooks get
        ``grace_seconds`` to finish on their own before the stragglers are
        cancelled. That is the right shape for a *per-run* teardown, where the
        manager may be shut down moments after a hook was dispatched and
        cancel-first would effectively disable async hooks for that caller.

        Waits at most ``grace_seconds`` per phase, so shutdown can never block on
        a hook that refuses to unwind. Safe to call when nothing is pending, and
        safe to call repeatedly.
        """
        if drain:
            await self._settle_background_hooks(grace_seconds)
        tasks = [task for task in self._background_tasks if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await self._settle_background_hooks(grace_seconds)
        # No unconditional clear() here: the done-callback already discards
        # finished tasks, so anything still in the set genuinely never settled and
        # has_pending_background_hooks must keep reporting it. Clearing made the
        # property claim "nothing pending" while hooks were still running.
        #
        # The semaphore is bound to the loop that created it; dropping it lets a
        # later session on a fresh loop build its own instead of awaiting a
        # semaphore attached to a closed one.
        self._bg_semaphore = None

    async def _settle_background_hooks(self, timeout: float) -> None:
        """Wait up to *timeout* for the pending background hooks to finish."""
        tasks = [task for task in self._background_tasks if not task.done()]
        if not tasks:
            return
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.debug(
                "%d background hook(s) did not settle within %ss",
                len(tasks),
                timeout,
            )

    async def _run_background_hook(
        self, hook: HookCallable, context: HookContext
    ) -> None:
        """Run a fire-and-forget hook under the concurrency semaphore."""
        if self._bg_semaphore is None:
            # Safe to create here: we are on the running loop and there is no
            # await between the check and the assignment.
            self._bg_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_BG_HOOKS)
        async with self._bg_semaphore:
            try:
                await hook(context)
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.debug("Background hook raised", exc_info=True)

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

        results: list[HookResult] = []
        for exec_result in exec_results:
            modifications = exec_result.data.copy() if exec_result.data else {}

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

        for factory in self._hook_factories:
            factory(self)

        for search_dir in target_search_dirs:
            self._load_from_path(search_dir)

        self._loaded = True

    def get_search_directories(self) -> list[str | Path]:
        """Directories searched for hook definitions, in precedence order.

        Project-level locations come before user-level ones, so a project hook
        overrides a home-directory hook of the same name.
        """
        return _get_search_directories()

    def _hydrate_hook(self, config: HookConfig) -> HookCallable:
        """
        Convert HookConfig into a HookCallable using appropriate executor.
        Wraps the actual hook with matcher evaluation.
        """
        if config.type == HookType.COMMAND:
            inner_hook = self._create_command_hook(
                cast("CommandHookConfig", config.config), config.timeout
            )
        elif config.type == HookType.PROMPT:
            inner_hook = self._create_prompt_hook(
                cast("PromptHookConfig", config.config)
            )
        elif config.type == HookType.AGENT:
            inner_hook = self._create_agent_hook(cast("AgentHookConfig", config.config))
        else:

            async def placeholder_hook(context: HookContext) -> HookResult:
                logger.warning(
                    f"Executing placeholder for hook '{config.name}' (Type: {config.type})."
                )
                return HookResult(success=True, output=f"Placeholder for {config.name}")

            inner_hook = placeholder_hook

        # Store config for debugging and timeout lookup
        self._hook_configs[config.name] = config

        # Create wrapper that evaluates matchers. Async fire-and-forget is NOT
        # handled here: this wrapper runs inside the thread executor's
        # short-lived `asyncio.run` loop, which would cancel a task spawned here
        # the moment it returns. `execute_hooks` dispatches async command hooks
        # on the persistent main loop instead (see there).
        async def hook_with_matchers(context: HookContext) -> HookResult:
            if not evaluate_matchers(config.matchers, context):
                logger.debug(
                    f"Hook '{config.name}' skipped due to matcher evaluation failure"
                )
                # Return a neutral result (not an error, just didn't run)
                return HookResult(success=True, output="Skipped due to matchers")

            return await inner_hook(context)

        return hook_with_matchers

    def _create_command_hook(
        self, config: CommandHookConfig, timeout: float | None = None
    ) -> HookCallable:
        return create_command_hook(config, timeout)

    def _create_prompt_hook(self, config: PromptHookConfig) -> HookCallable:
        return create_prompt_hook(config)

    def _create_agent_hook(self, config: AgentHookConfig) -> HookCallable:
        return create_agent_hook(config)


# Module-level singleton - lightweight, hooks loaded on first execute_hooks() call
hook_manager = HookManager()
