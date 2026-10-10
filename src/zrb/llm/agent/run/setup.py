"""Pure setup helpers for the agent run loop.

Resolves the effective UI / tool-confirmation / yolo / approval-channel /
hook-manager dependencies, binds run-scoped ``ContextVar``s, logs the startup
state, and wires the print + event handlers. Extracted from ``runner.py`` so the
run loop itself stays focused on driving ``pydantic_ai.Agent``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.llm.agent_state import (
    current_hook_manager,
    current_model,
    current_small_model,
    current_tool_confirmation,
    current_ui,
    current_yolo,
)
from zrb.llm.approval.approval_channel import current_approval_channel
from zrb.llm.approval.multiplex_approval_channel import MultiplexApprovalChannel
from zrb.llm.approval.terminal_approval_channel import TerminalApprovalChannel
from zrb.llm.hook.manager import hook_manager as default_hook_manager
from zrb.llm.ui.multi_ui import MultiUI, create_combined_ui
from zrb.llm.ui.std_ui import StdUI
from zrb.util.contextvar_scope import scoped

if TYPE_CHECKING:
    from zrb.llm.ui.any_ui import AnyUI


def bind_contextvar(stack: ExitStack, var: ContextVar, value: Any) -> None:
    """Bind `var` to `value` for the life of `stack` (via `scoped()`).

    Keeps ContextVar set/reset symmetric and exception-safe across the run.
    """
    stack.enter_context(scoped(var, value))


@contextmanager
def session_model_scope(ui: "AnyUI | list[AnyUI] | None") -> "Iterator[None]":
    """Bind a session's model overrides — `/model small` and `/model` — as a run does.

    A run binds these while it runs (`runner.py`), which is what makes
    `/model small <name>` reach the model resolver's precedence chain. A path
    that resolves a model *outside* a run has to bind them itself or it falls
    through to `CFG` — `/compress` is handled by the task before `run_agent`
    exists, and the summarizer is the consumer users most expect `/model small`
    to reach.

    *ui* is the session's UI, or the list of UIs a task holds; a list is
    combined exactly as `resolve_context_dependencies` combines it, so both
    paths see the same UI.

    Only non-`None` values are bound, so an enclosing run's binding is never
    replaced by nothing.
    """
    effective_ui = None if ui is None else create_combined_ui(ui, fallback=StdUI())
    with ExitStack() as stack:
        small_model = getattr(effective_ui, "small_model", None)
        if small_model is not None:
            bind_contextvar(stack, current_small_model, small_model)
        model = getattr(effective_ui, "model", None)
        if model is not None:
            bind_contextvar(stack, current_model, model)
        yield


def resolve_context_dependencies(
    ui, tool_confirmation, yolo, approval_channel, hook_manager
):
    ui_arg = ui if ui is not None else current_ui.get()
    if ui_arg is None:
        ui_arg = StdUI()
    effective_ui = create_combined_ui(ui_arg, fallback=StdUI())

    effective_tool_confirmation = tool_confirmation or current_tool_confirmation.get()
    # A nested run inherits the manager its parent is running on, the way it
    # already inherits the UI, the confirmation mode and the approval channel.
    # Falling straight through to the singleton made a sub-agent's own
    # PreToolUse/Stop fire on the process-wide manager, so a deny rule a task
    # registered with `append_hook_factory` did not bind a delegated
    # sub-agent's tools.
    effective_hook_manager = (
        hook_manager or current_hook_manager.get() or default_hook_manager
    )
    # None = inherit the parent run's YOLO state; an explicit False must stay
    # False (a nested run opting out) — `yolo or current_yolo.get()` would
    # coerce that False back into inheritance instead.
    effective_yolo = yolo if yolo is not None else current_yolo.get()
    effective_approval_channel = approval_channel or current_approval_channel.get()

    if effective_approval_channel is not None and effective_ui is not None:
        if not isinstance(effective_approval_channel, MultiplexApprovalChannel):
            ui_for_terminal = effective_ui
            if isinstance(effective_ui, MultiUI) and effective_ui.main_ui is not None:
                ui_for_terminal = effective_ui.main_ui
            CFG.LOGGER.debug(
                f"Creating TerminalApprovalChannel with UI: {ui_for_terminal}"
            )
            terminal_channel = TerminalApprovalChannel(ui_for_terminal)
            effective_approval_channel = MultiplexApprovalChannel(
                [terminal_channel, effective_approval_channel]
            )
            CFG.LOGGER.debug("Wrapped approval channel: CLI first, then Telegram")

    return (
        effective_ui,
        effective_tool_confirmation,
        effective_yolo,
        effective_approval_channel,
        effective_hook_manager,
    )


def log_startup(
    tool_confirmation,
    effective_tool_confirmation,
    approval_channel,
    effective_approval_channel,
):
    CFG.LOGGER.debug("run_agent === START ===")
    CFG.LOGGER.debug(f"tool_confirmation param: {tool_confirmation}")
    CFG.LOGGER.debug(
        f"current_tool_confirmation.get(): {current_tool_confirmation.get()}"
    )
    CFG.LOGGER.debug(f"effective_tool_confirmation: {effective_tool_confirmation}")
    CFG.LOGGER.debug(f"approval_channel param: {approval_channel}")
    CFG.LOGGER.debug(
        f"current_approval_channel.get(): {current_approval_channel.get()}"
    )
    CFG.LOGGER.debug(f"effective_approval_channel: {effective_approval_channel}")


def setup_print_and_events(print_fn, event_handler, effective_ui):
    effective_print_fn = print_fn
    if effective_print_fn == print and effective_ui:
        effective_print_fn = effective_ui.append_to_output

    effective_event_handler = event_handler
    if effective_event_handler is None:
        # lazy: zrb.llm.util.stream_response transitively pulls pydantic_ai;
        # keeping this lazy preserves cold-start latency.
        from zrb.llm.util.stream_response import create_event_handler

        def _event_print_fn(text: str, kind: str) -> None:
            effective_ui.append_to_output(text, end="", kind=kind)

        effective_event_handler = create_event_handler(
            _event_print_fn,
            show_tool_call_detail=CFG.LLM_SHOW_TOOL_CALL_DETAIL,
            show_tool_result=CFG.LLM_SHOW_TOOL_CALL_RESULT,
            usage_callback=getattr(effective_ui, "accumulate_usage", None),
            tool_block_recorder=getattr(effective_ui, "record_tool_call_block", None),
            on_thinking_start=getattr(effective_ui, "mark_thinking_block_start", None),
            on_thinking_collapse=getattr(effective_ui, "collapse_thinking_block", None),
            on_text_start=getattr(effective_ui, "mark_text_block_start", None),
            on_text_collapse=getattr(effective_ui, "collapse_text_block", None),
            on_tool_prepare_update=getattr(effective_ui, "update_tool_prepare", None),
            on_tool_call_start=getattr(effective_ui, "start_tool_call", None),
            on_tool_call_end=getattr(effective_ui, "end_tool_call", None),
        )
    return effective_print_fn, effective_event_handler
