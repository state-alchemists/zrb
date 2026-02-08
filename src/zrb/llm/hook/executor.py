"""
Thread-safe hook executor with timeout controls and proper error handling.
Implements Claude Code compatible execution patterns.
"""

import asyncio
import concurrent.futures
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from zrb.llm.hook.interface import HookCallable, HookContext, HookResult
from zrb.llm.hook.types import HookEvent

logger = logging.getLogger(__name__)


@dataclass
class HookExecutionResult:
    """Enhanced result with Claude Code compatibility fields."""

    success: bool
    blocked: bool = False
    message: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    exit_code: int = 0
    decision: Optional[str] = None  # "block", "allow", "deny", "ask"
    reason: Optional[str] = None
    permission_decision: Optional[str] = None  # "allow", "deny", "ask"
    permission_decision_reason: Optional[str] = None
    additional_context: Optional[str] = None
    updated_input: Optional[Dict[str, Any]] = None
    system_message: Optional[str] = None
    continue_execution: bool = True
    suppress_output: bool = False
    hook_specific_output: Optional[Dict[str, Any]] = None


class ThreadPoolHookExecutor:
    """
    Thread-safe executor for hook execution with timeout controls.

    Implements Claude Code compatible execution patterns:
    - Thread pool with size limits
    - Timeout controls per hook
    - Graceful shutdown
    - Proper error propagation
    - Exit code handling (0=success, 2=block)
    """

    def __init__(self, max_workers: int = 10, default_timeout: int = 30):
        self.max_workers = max_workers
        self.default_timeout = default_timeout
        self._executor: Optional[ThreadPoolExecutor] = None
        self._lock = threading.RLock()
        self._shutdown_event = threading.Event()

    def start(self):
        """Start the thread pool executor."""
        with self._lock:
            if self._executor is None:
                self._executor = ThreadPoolExecutor(
                    max_workers=self.max_workers, thread_name_prefix="zrb-hook-"
                )
                self._shutdown_event.clear()
                logger.debug(f"Hook executor started with {self.max_workers} workers")

    def shutdown(self, wait: bool = True):
        """Shutdown the thread pool executor."""
        with self._lock:
            if self._executor is not None:
                self._shutdown_event.set()
                self._executor.shutdown(wait=wait)
                self._executor = None
                logger.debug("Hook executor shutdown complete")

    @asynccontextmanager
    async def execution_context(self):
        """Context manager for hook execution."""
        try:
            self.start()
            yield self
        finally:
            # Don't shutdown automatically - let the manager handle lifecycle
            pass

    async def execute_hook(
        self,
        hook: HookCallable,
        context: HookContext,
        timeout: Optional[int] = None,
    ) -> HookExecutionResult:
        """
        Execute a hook with timeout and proper error handling.

        Args:
            hook: The hook callable to execute
            context: Hook context with event data
            timeout: Timeout in seconds (defaults to self.default_timeout)

        Returns:
            HookExecutionResult with Claude Code compatible fields
        """
        if self._shutdown_event.is_set():
            return HookExecutionResult(
                success=False, error="Hook executor is shutting down", exit_code=1
            )

        timeout = timeout or self.default_timeout

        try:
            # Run hook in thread pool with timeout
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    self._executor, self._run_hook_sync, hook, context
                ),
                timeout=timeout,
            )
            return result

        except asyncio.TimeoutError:
            logger.warning(f"Hook execution timed out after {timeout}s")
            return HookExecutionResult(
                success=False,
                error=f"Hook execution timed out after {timeout}s",
                exit_code=124,  # Standard timeout exit code
            )
        except Exception as e:
            logger.error(f"Error executing hook: {e}", exc_info=True)
            return HookExecutionResult(success=False, error=str(e), exit_code=1)

    def _run_hook_sync(
        self, hook: HookCallable, context: HookContext
    ) -> HookExecutionResult:
        """
        Run hook synchronously in thread pool.
        This method handles the actual execution and result parsing.

        Uses asyncio.run() for proper event loop lifecycle management
        to avoid "Event loop is closed" errors during subprocess transport cleanup.
        """

        async def run_hook_async():
            """Wrapper to run the hook and handle exceptions."""
            try:
                return await hook(context)
            except Exception as e:
                logger.error(f"Error in hook execution: {e}", exc_info=True)
                # Return a failure result instead of raising
                return HookResult(success=False, output=str(e), should_stop=False)

        try:
            # Use asyncio.run() which properly handles event loop lifecycle
            # including cleanup of subprocess transports
            hook_result = asyncio.run(run_hook_async())

            # Parse result into Claude Code compatible format
            return self._parse_hook_result(hook_result)

        except Exception as e:
            logger.error(f"Error in hook execution setup: {e}", exc_info=True)
            return HookExecutionResult(success=False, error=str(e), exit_code=1)

    def _parse_hook_result(self, result: HookResult) -> HookExecutionResult:
        """
        Parse Zrb HookResult into Claude Code compatible HookExecutionResult.

        Claude Code uses:
        - exit_code: 0=success, 2=block
        - decision: "block" for blocking decisions
        - hook_specific_output for event-specific control
        """
        # Start with basic success/failure
        exec_result = HookExecutionResult(
            success=result.success, message=result.output, data=result.data or {}
        )

        # Check for blocking decisions
        if result.should_stop:
            exec_result.blocked = True
            exec_result.decision = "block"
            exec_result.exit_code = 2

        # Parse modifications for Claude Code compatibility
        if result.modifications:
            # Check for Claude Code specific fields
            if "decision" in result.modifications:
                exec_result.decision = result.modifications["decision"]
                if exec_result.decision == "block":
                    exec_result.blocked = True
                    exec_result.exit_code = 2

            if "reason" in result.modifications:
                exec_result.reason = result.modifications["reason"]

            if "permissionDecision" in result.modifications:
                exec_result.permission_decision = result.modifications[
                    "permissionDecision"
                ]

            if "permissionDecisionReason" in result.modifications:
                exec_result.permission_decision_reason = result.modifications[
                    "permissionDecisionReason"
                ]

            if "additionalContext" in result.modifications:
                exec_result.additional_context = result.modifications[
                    "additionalContext"
                ]

            if "updatedInput" in result.modifications:
                exec_result.updated_input = result.modifications["updatedInput"]

            if "systemMessage" in result.modifications:
                exec_result.system_message = result.modifications["systemMessage"]

            if "continue" in result.modifications:
                exec_result.continue_execution = result.modifications["continue"]

            if "suppressOutput" in result.modifications:
                exec_result.suppress_output = result.modifications["suppressOutput"]

            # Check for hookSpecificOutput (Claude Code format)
            if "hookSpecificOutput" in result.modifications:
                exec_result.hook_specific_output = result.modifications[
                    "hookSpecificOutput"
                ]

        return exec_result

    def create_claude_compatible_result(
        self,
        success: bool = True,
        blocked: bool = False,
        message: Optional[str] = None,
        decision: Optional[str] = None,
        reason: Optional[str] = None,
        permission_decision: Optional[str] = None,
        permission_decision_reason: Optional[str] = None,
        additional_context: Optional[str] = None,
        updated_input: Optional[Dict[str, Any]] = None,
        system_message: Optional[str] = None,
        continue_execution: bool = True,
        suppress_output: bool = False,
        exit_code: int = 0,
    ) -> HookExecutionResult:
        """
        Create a Claude Code compatible hook result.

        This is a helper for hook implementations to ensure compatibility.
        """
        return HookExecutionResult(
            success=success,
            blocked=blocked,
            message=message,
            decision=decision,
            reason=reason,
            permission_decision=permission_decision,
            permission_decision_reason=permission_decision_reason,
            additional_context=additional_context,
            updated_input=updated_input,
            system_message=system_message,
            continue_execution=continue_execution,
            suppress_output=suppress_output,
            exit_code=exit_code,
        )


# Singleton instance
_hook_executor: Optional[ThreadPoolHookExecutor] = None


def get_hook_executor() -> ThreadPoolHookExecutor:
    """Get or create the singleton hook executor."""
    global _hook_executor
    if _hook_executor is None:
        _hook_executor = ThreadPoolHookExecutor()
        _hook_executor.start()
    return _hook_executor


def shutdown_hook_executor(wait: bool = True):
    """Shutdown the singleton hook executor."""
    global _hook_executor
    if _hook_executor is not None:
        _hook_executor.shutdown(wait=wait)
        _hook_executor = None
