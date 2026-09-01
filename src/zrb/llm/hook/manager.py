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

# Stand-in priority (0) for hooks with no config (e.g. manually registered),
# so they sort predictably alongside configured hooks instead of erroring.
# Read-only — never mutated — so one shared instance is safe across calls.
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
        registry: HookRegistry | None = None,
        search_dirs: list[str | Path] | None = None,
        max_depth: int = 1,
        ignore_dirs: list[str] | None = None,
    ):
        # Lightweight: just assign properties, no heavy operations
        """Discover, register, and run lifecycle hooks.

        Decomposed per ADR-0090: the manager owns discovery, hydration,
        execution, and factory seeding, and composes a `HookRegistry` for the
        canonical hook collection. Registration and every query delegate to the
        registry.

        Args:
            registry: The canonical `HookRegistry` to read and write. A fresh
                registry is created when `None`, giving an isolated view.
            search_dirs: Directories to scan for hook definitions. Defaults to
                the standard project and user locations.
            max_depth: How many directory levels below each search directory to
                descend.
            ignore_dirs: Directory names skipped while scanning, such as
                `node_modules`.
        """
        self._registry = registry if registry is not None else HookRegistry()
        self._executor: ThreadPoolHookExecutor = get_hook_executor()
        # `register_journal_compliance_hook` ships as a *default* factory on
        # every instance, not just the module-level singleton below — a real
        # chat run's `Stop` event dispatches through a fresh, per-run
        # `HookManager()` (`_create_llm_task_core` builds one whenever the
        # task's own `hook_manager` is unset), never through the singleton.
        # Discovered by running a real turn end-to-end: the factory-attached
        # singleton logged the hook as "registered" (a *different* manager
        # instance, used only for PreToolUse/PostToolUse via the ambient
        # ContextVar lookup, picked it up), but the manager that actually
        # fired Stop had `_hook_factories == []` and never ran it. File-backed
        # hooks (settings.json/hooks.json) don't have this problem because
        # every manager independently re-scans the filesystem; a Python-
        # registered one needs to be seeded the same way on every instance.
        self._hook_factories: list[Callable[[HookManager], None]] = [
            register_journal_compliance_hook
        ]
        self._max_depth = max_depth
        self._ignore_dirs = _IGNORE_DIRS if ignore_dirs is None else ignore_dirs
        self._search_dirs: list[str | Path] | None = search_dirs
        self._loaded: bool = False
        # Strong refs to fire-and-forget async hook tasks so the event loop
        # doesn't GC them mid-run (asyncio only keeps weak references).
        self._background_tasks: set[asyncio.Task] = set()
        # Which hook each pending background task came from, so shutdown()
        # can look up that hook's own configured timeout (see
        # _effective_grace_seconds) instead of always using the flat default.
        self._background_task_hook: dict[asyncio.Task, HookCallable] = {}
        # Bounds concurrent fire-and-forget subprocesses. Created lazily inside
        # the running loop (see _run_background_hook).
        self._bg_semaphore: asyncio.Semaphore | None = None

    @property
    def registry(self) -> HookRegistry:
        """The canonical hook collection this manager reads and writes."""
        return self._registry

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
        self._registry.clear_manual()
        # _ensure_loaded -> _scan_and_load already runs _hook_factories; no
        # separate loop here, or every factory would run twice.
        self._ensure_loaded()

    def _scan_and_load(self):
        """Internal: scan filesystem and load hooks without resetting existing ones.

        Runs `_hook_factories` too — the lazy path (`_ensure_loaded`, taken on
        the first `execute_hooks()` call) previously skipped them, so a
        factory only ever fired if something called the public `scan()` or
        `reload()` — which nothing in a normal chat session does. That made
        `add_hook_factory` dead in practice for the default singleton.
        """
        for factory in self._hook_factories:
            factory(self)

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
        self._registry.register(hook, events, config)

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

        # Async command AND agent hooks are fire-and-forget: spawn them on the
        # current (persistent) event loop and DON'T await. Awaiting them
        # through the thread executor would block here until the hook's
        # subprocess (or, for an agent hook, its LLM call) — and any child a
        # command hook forks, e.g. peon-ping's audio player — exits or the
        # timeout fires, defeating the whole point of `async` and stalling
        # the agent on every event (a per-output-chunk Notification hook
        # alone would add a multi-second wait per chunk; an agent-type Stop
        # hook would add a full extra model round-trip to every matching
        # turn). They cannot block or contribute additionalContext, so
        # omitting their result is correct.
        is_background_eligible = (
            config is not None
            and config.is_async
            and config.type in (HookType.COMMAND, HookType.AGENT)
        )
        if is_background_eligible:
            # Check matchers before spawning, not after: `hook` (matcher-
            # wrapped by `_wrap_with_matchers`) would otherwise still get
            # spawned as a background task on every firing of its event even
            # when it's about to reject itself and return instantly. Wasted
            # background-task churn for any hook, and actively wrong for an
            # agent-type one: its (correctly generous) `timeout` would count
            # toward `_effective_grace_seconds`'s shared batch wait even on
            # turns where it was never going to run, silently extending the
            # drain for every *other* pending hook too. A rejected background
            # hook still contributes no result, same as one that ran —
            # unlike a rejected *synchronous* hook below, which does.
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

        # Check for blocking decisions (exit code 2). A block only halts the
        # chain for events that can actually be blocked; for any other event
        # the block is a no-op signal, so we keep running the remaining hooks
        # (Claude-compatible — exit 2 is meaningful only where the lifecycle
        # can be stopped).
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

        # Check for continue=false (an explicit "stop all processing" request,
        # honored for every event regardless of whether it can be blocked).
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

        `grace_seconds`'s default (2.0) was tuned for what async hooks used to
        be: a subprocess playing a sound, an `echo`. An `agent`-type hook
        makes a real LLM round-trip — measured at ~15s for a two-step
        tool-calling exchange even on a small/fast model — so draining every
        hook under one flat short window would cancel it before it ever gets
        to act.

        Scoped to `HookType.AGENT` on purpose, not every hook: `config.timeout`
        is shared with the synchronous executor's own per-hook timeout, and a
        command hook's default there is 600s (a long-running shell script is
        normal) — extending the *drain* wait to match would turn "cancel a
        runaway background hook at teardown" into "wait up to ten minutes for
        it," which defeats the bound this method exists to keep. Only agent
        hooks get a real reason to need longer than the flat default here.
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
            await self._settle_background_hooks(
                self._effective_grace_seconds(grace_seconds)
            )
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
        inner_hook = self._select_inner_hook(config)
        # Store config for debugging and timeout lookup
        self._registry.record_config(config.name, config)
        return self._wrap_with_matchers(inner_hook, config)

    def _select_inner_hook(self, config: HookConfig) -> HookCallable:
        """Build the callable for `config.type` (command/prompt/agent), or a
        logging placeholder for anything else."""
        # lazy: zrb internal (heavy via transitive) — this edge isn't itself
        # circular, but hook.creator's own create_agent import used to be
        # (zrb.llm.agent's package __init__ reaches this method's module,
        # zrb.llm.hook.manager, at module level). Deferring this import
        # (and agent/hook_agent.py's matching one) keeps hook.creator out of
        # zrb.llm.agent's eager import closure entirely, verified by walking
        # that closure — not just by checking this one call site — so its
        # own create_agent import no longer needs the circular workaround.
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
                # Return a neutral result (not an error, just didn't run)
                return HookResult(success=True, output="Skipped due to matchers")

            return await inner_hook(context)

        return hook_with_matchers


# Module-level singleton - lightweight, hooks loaded on first execute_hooks() call
hook_manager = HookManager(registry=hook_registry)
