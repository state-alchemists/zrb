"""`HookManager` — Claude-Code-compatible lifecycle hooks.

Owns hook registration, matcher evaluation, and execution. The filesystem
loading + JSON/YAML parsing lives in the sibling `manager_loading.py`; the
type-specific factories (command/prompt/agent) live in `zrb.llm.hook.creator`;
matcher operator semantics live in `zrb.llm.hook.matcher`.

For the public hook authoring guide (formats, events, examples), see:
  docs/llm/hooks.md
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Callable, cast

from zrb.config.config import CFG
from zrb.llm.hook.agent_hook_registry import get_agent_hook_builder
from zrb.llm.hook.executor import (
    HookExecutionResult,
    ThreadPoolHookExecutor,
    get_hook_executor,
)
from zrb.llm.hook.hook_loader import get_search_directories as _get_search_directories
from zrb.llm.hook.interface import HookCallable, HookContext, HookResult
from zrb.llm.hook.journal_compliance import register_journal_compliance_hook
from zrb.llm.hook.manager_loading import HookManagerLoading
from zrb.llm.hook.matcher import evaluate_matchers
from zrb.llm.hook.registry import HookRegistry, hook_registry
from zrb.llm.hook.schema import (
    AgentHookConfig,
    CommandHookConfig,
    HookConfig,
    PromptHookConfig,
)
from zrb.llm.hook.self_review import register_self_review_hook
from zrb.llm.hook.types import BLOCKING_EVENTS, HookEvent, HookType

logger = logging.getLogger(__name__)

_IGNORE_DIRS: list[str] = []

# Bound fire-and-forget hooks: an unbounded pile of subprocesses from a
# high-frequency event exhausts file descriptors and, behind a serialized
# external tool, causes a timeout storm. The semaphore caps concurrency; the
# pending ceiling drops new hooks once the backlog is full.
_MAX_CONCURRENT_BG_HOOKS = 4
_MAX_PENDING_BG_HOOKS = 64

# Stand-in (priority 0) for hooks with no config, e.g. manually registered.
# Never mutated, so one shared instance is safe.
_DEFAULT_HOOK_CONFIG = HookConfig(
    name="default",
    events=[],
    type=HookType.COMMAND,
    config=CommandHookConfig(command=""),
    priority=0,
)


class HookManager(HookManagerLoading):
    def __init__(
        self,
        search_dirs: list[str | Path] | None = None,
        max_depth: int = 1,
        ignore_dirs: list[str] | None = None,
        registry: HookRegistry | None = None,
    ):
        """Discover, register, and run lifecycle hooks.

        The manager owns discovery, hydration, execution, and factory seeding;
        registration and every query delegate to the composed `HookRegistry`.

        Args:
            search_dirs: Directories to scan for hook definitions. Defaults to
                the standard project and user locations.
            max_depth: How many directory levels below each search directory to
                descend.
            ignore_dirs: Directory names skipped while scanning, such as
                `node_modules`.
            registry: The canonical `HookRegistry` to read and write. A fresh
                registry is created when `None`, giving an isolated view.
        """
        self._registry = registry if registry is not None else HookRegistry()
        self._executor: ThreadPoolHookExecutor = get_hook_executor()
        # Seeded on every instance, not just the singleton: a chat run's Stop
        # event fires on a fresh per-run `HookManager()`, which never sees the
        # singleton's registrations. File-backed hooks need no seeding because
        # every manager re-scans the filesystem.
        self._hook_factories: list[Callable[[HookManager], None]] = [
            register_journal_compliance_hook,
            register_self_review_hook,
        ]
        self._max_depth = max_depth
        self._ignore_dirs = _IGNORE_DIRS if ignore_dirs is None else ignore_dirs
        self._search_dirs: list[str | Path] | None = search_dirs
        self._loaded: bool = False
        # Strong refs: asyncio keeps only weak references to tasks.
        self._background_tasks: set[asyncio.Task] = set()
        # Lets shutdown() find each pending task's configured timeout.
        self._background_task_hook: dict[asyncio.Task, HookCallable] = {}
        # Created lazily inside the running loop (see _run_background_hook).
        self._bg_semaphore: asyncio.Semaphore | None = None

    @property
    def registry(self) -> HookRegistry:
        """The canonical hook collection this manager reads and writes."""
        return self._registry

    @property
    def search_dirs(self) -> list[str | Path]:
        """Directories scanned for hook files, in precedence order.

        The explicit override passed at construction (or set here), or the
        standard project and user locations when none was given. Assigning
        invalidates the load, so the next access rescans — which is how a
        caller points an already-constructed manager somewhere else (an empty
        list being the way to say "discover nothing").
        """
        if self._search_dirs is not None:
            return list(self._search_dirs)
        return self._default_search_dirs()

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
        self._registry.clear()
        self._ensure_loaded()

    def _scan_and_load(self, search_dirs: list[str | Path] | None = None):
        """Run the hook factories, then load hooks from *search_dirs*.

        Existing registrations are kept. The factories run here because the
        lazy path (`_ensure_loaded`) is the only one a normal chat session
        takes.
        """
        for factory in self._hook_factories:
            factory(self)
        for search_dir in self.search_dirs if search_dirs is None else search_dirs:
            self._load_from_path(search_dir)

    def add_hook(
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
        self._registry.add_hook(hook, events, config)

    def remove_hook(self, hook: HookCallable) -> None:
        """Unregister *hook* from every event and the global list."""
        self._registry.remove_hook(hook)

    def remove_event_hooks(self, event: HookEvent) -> None:
        """Unregister every hook for *event* (global hooks untouched)."""
        self._registry.remove_event_hooks(event)

    def set_hooks(
        self,
        event: HookEvent,
        hooks: list[HookCallable],
        configs: dict[HookCallable, HookConfig] | None = None,
    ) -> None:
        """Replace the hook list for *event* — a clean-slate swap.

        *configs* maps each hook to its `HookConfig`, repopulating the
        registry's config bookkeeping for the new set.
        """
        self._registry.set_hooks(event, hooks, configs)

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
        # Global kill-switch: no hook fires and the filesystem is never scanned.
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

        hooks_to_run = self._registry.get_global_hooks() + self._registry.get_hooks(
            event
        )

        if not hooks_to_run:
            return results

        hooks_to_run = self._sort_hooks_by_priority(hooks_to_run)

        # Sequential, not concurrent: a hook may block or stop the chain.
        for i, hook in enumerate(hooks_to_run):
            result, stop = await self._run_one_hook(i, hook, event, context)
            if result is not None:
                results.append(result)
            if stop:
                return results

        return results

    def _sort_hooks_by_priority(self, hooks: list[HookCallable]) -> list[HookCallable]:
        """Higher `priority` runs first; a hook with no config sorts as 0."""
        return sorted(
            hooks,
            key=lambda h: self._registry.get_hook_config(
                h, _DEFAULT_HOOK_CONFIG
            ).priority,
            reverse=True,
        )

    async def _run_one_hook(
        self,
        index: int,
        hook: HookCallable,
        event: HookEvent,
        context: HookContext,
    ) -> tuple[HookExecutionResult | None, bool]:
        """Run one hook. Returns `(result, stop)`.

        `result` is `None` only when an async command hook was spawned
        fire-and-forget (nothing to record). `stop` is True when
        `execute_hooks` must return immediately after this result — a block
        on a blockable event, or an explicit `continue=false`.
        """
        config = self._registry.get_hook_config(hook)
        timeout = config.timeout if config else None

        # Async command and agent hooks are fire-and-forget on the persistent
        # loop: awaiting them would stall the agent until the subprocess (and
        # its children) or LLM call finishes. They cannot block or contribute
        # additionalContext, so they record no result.
        is_background_eligible = (
            config is not None
            and config.is_async
            and config.type in (HookType.COMMAND, HookType.AGENT)
        )
        if is_background_eligible:
            # Match before spawning: a spawned-then-rejected agent hook would
            # still extend `_effective_grace_seconds`'s drain for every other
            # pending hook.
            assert config is not None
            if not evaluate_matchers(config.matchers, context):
                return None, False
            if self._spawn_background_hook(hook, context):
                return None, False
            # No running loop (rare sync caller) — fall through to the
            # executor so the hook still runs, just synchronously.

        try:
            result = await self._executor.execute_hook(hook, context, timeout=timeout)
        except Exception as e:
            logger.error(
                f"Error executing hook {index} for event {event}: {e}",
                exc_info=True,
            )
            return HookExecutionResult(success=False, error=str(e), exit_code=1), False

        # A block (exit code 2) halts the chain only for blockable events,
        # matching Claude Code.
        if result.blocked or result.exit_code == 2:
            if event in BLOCKING_EVENTS:
                logger.info(
                    f"Hook blocked execution. Stopping further hooks for event {event}."
                )
                return result, True
            logger.debug(
                f"Hook returned a block for non-blocking event {event}; "
                "ignoring block and continuing remaining hooks."
            )

        # continue=false stops processing for every event.
        if not result.continue_execution:
            logger.info(f"Hook requested stop of all processing for event {event}.")
            return result, True

        return result, False

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
        self._background_task_hook[task] = hook
        task.add_done_callback(self._background_tasks.discard)
        task.add_done_callback(lambda t: self._background_task_hook.pop(t, None))
        return True

    def _effective_grace_seconds(self, fallback: float) -> float:
        """The grace period to actually wait during a drain — extended to the
        largest `timeout` configured among currently-pending **agent-type**
        hooks specifically, or *fallback* if there are none.

        An agent hook makes an LLM round-trip, too slow for the flat default
        that suits a cheap command hook. Command hooks are excluded because
        their `timeout` (default 600s) is the synchronous executor's limit,
        and waiting that long at teardown would defeat the bound.
        """
        configured = [
            cfg.timeout
            for task in self._background_tasks
            if not task.done()
            and (hook := self._background_task_hook.get(task)) is not None
            and (cfg := self._registry.get_hook_config(hook)) is not None
            and cfg.type == HookType.AGENT
            and cfg.timeout is not None
        ]
        return max([fallback, *configured]) if configured else fallback

    @property
    def has_pending_background_hooks(self) -> bool:
        """True while any fire-and-forget hook task is still running."""
        return any(not task.done() for task in self._background_tasks)

    @property
    def background_tasks(self) -> "set[asyncio.Task]":
        """Fire-and-forget hook tasks currently in flight."""
        return self._background_tasks

    async def shutdown(
        self, grace_seconds: float = 2.0, *, drain: bool = False
    ) -> None:
        """Cancel in-flight fire-and-forget hooks and wait for them to settle.

        Async hook subprocesses run in their own process group, so Ctrl+C does
        not reach them; cancelling the task makes the command hook's
        cancellation handler kill its process tree. Cancelling up front keeps
        exit snappy.

        ``drain=True`` first gives pending hooks ``grace_seconds`` to finish on
        their own — for a per-run teardown, where cancel-first would disable
        async hooks dispatched moments earlier.

        Waits at most ``grace_seconds`` per phase, so shutdown can never block on
        a hook that refuses to unwind. Safe to call when nothing is pending, and
        safe to call repeatedly.
        """
        if drain:
            await self._settle_background_hooks(
                self._effective_grace_seconds(grace_seconds)
            )
        tasks = [task for task in self._background_tasks if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await self._settle_background_hooks(grace_seconds)
        # No clear(): the done-callback discards finished tasks, so anything
        # left never settled and has_pending_background_hooks must report it.
        # The semaphore is bound to its loop; a later session builds its own.
        self._bg_semaphore = None

    async def _settle_background_hooks(self, timeout: float) -> None:
        """Wait up to *timeout* for the pending background hooks to finish."""
        tasks = [task for task in self._background_tasks if not task.done()]
        if not tasks:
            return
        # INFO, not debug: this wait can run up to an agent hook's own timeout
        # (60s for the built-in journal-compliance judge) at the exit of a
        # one-shot `zrb llm chat` — without this line that looks like a hang.
        logger.info(
            "Waiting up to %ss for %d background hook(s) to finish...",
            timeout,
            len(tasks),
        )
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
        """Run *event*'s hooks and flatten each result into a `HookResult`.

        `execute_hooks` returns typed execution results; this collapses each
        one's fields into the flat, Claude-format `modifications` mapping
        (`decision`, `permissionDecision`, `additionalContext`, `updatedInput`,
        …) that `HookResult` carries.

        Nothing in zrb itself calls this — the runtime consumes the typed form
        directly. It exists for callers that want the flat shape.
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
        """Register *factory*, called on every load/reload so it can register
        hooks conditionally (e.g. on config) rather than unconditionally at
        construction time."""
        self._hook_factories.append(factory)

    def scan(self, search_dirs: list[str | Path] | None = None):
        """
        Scan for hooks in default locations and provided directories.
        This method can be called manually to add filesystem hooks.
        Does NOT clear manually registered hooks.
        """
        self._scan_and_load(search_dirs)
        self._loaded = True

    def _default_search_dirs(self) -> list[str | Path]:
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
        inner_hook = self._select_inner_hook(config)
        self._registry.record_config(config.name, config)
        return self._wrap_with_matchers(inner_hook, config)

    def _select_inner_hook(self, config: HookConfig) -> HookCallable:
        """Build the callable for `config.type` (command/prompt/agent), or a
        logging placeholder for anything else."""
        # lazy: zrb internal (heavy via transitive). Deferring this and
        # agent/hook_agent.py's matching import keeps hook.creator out of
        # zrb.llm.agent's eager import closure; hoisting either puts it back.
        from zrb.llm.hook.creator import create_command_hook, create_prompt_hook

        if config.type == HookType.COMMAND:
            return create_command_hook(
                cast("CommandHookConfig", config.config), config.timeout
            )
        if config.type == HookType.PROMPT:
            return create_prompt_hook(cast("PromptHookConfig", config.config))
        if config.type == HookType.AGENT:
            builder = get_agent_hook_builder()
            if builder is not None:
                return builder(cast("AgentHookConfig", config.config))

            async def unavailable_hook(context: HookContext) -> HookResult:
                logger.warning(
                    f"Agent-type hook '{config.name}' skipped: zrb.llm.agent was "
                    "never imported in this process."
                )
                return HookResult(success=False, output="Agent hooks unavailable")

            return unavailable_hook

        async def placeholder_hook(context: HookContext) -> HookResult:
            logger.warning(
                f"Executing placeholder for hook '{config.name}' (Type: {config.type})."
            )
            return HookResult(success=True, output=f"Placeholder for {config.name}")

        return placeholder_hook

    def _wrap_with_matchers(
        self, inner_hook: HookCallable, config: HookConfig
    ) -> HookCallable:
        """Wrap `inner_hook` so it only runs when `config.matchers` passes.

        Async fire-and-forget is NOT handled here: this wrapper runs inside
        the thread executor's short-lived `asyncio.run` loop, which would
        cancel a task spawned here the moment it returns. `execute_hooks`
        dispatches async command hooks on the persistent main loop instead
        (see there).
        """

        async def hook_with_matchers(context: HookContext) -> HookResult:
            if not evaluate_matchers(config.matchers, context):
                logger.debug(
                    f"Hook '{config.name}' skipped due to matcher evaluation failure"
                )
                return HookResult(success=True, output="Skipped due to matchers")

            return await inner_hook(context)

        return hook_with_matchers


# Module-level singleton - lightweight, hooks loaded on first execute_hooks() call
hook_manager = HookManager(registry=hook_registry)
