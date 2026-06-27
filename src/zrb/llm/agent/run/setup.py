"""Pure setup helpers for the agent run loop.

Resolves the effective UI / tool-confirmation / yolo / approval-channel /
hook-manager dependencies, binds run-scoped ``ContextVar``s, logs the startup
state, and wires the print + event handlers. Extracted from ``runner.py`` so the
run loop itself stays focused on driving ``pydantic_ai.Agent``.
"""

from __future__ import annotations

from contextlib import ExitStack
from contextvars import ContextVar
from typing import Any

from zrb.config.config import CFG
from zrb.llm.approval.approval_channel import current_approval_channel
from zrb.llm.hook.manager import hook_manager as default_hook_manager


def _bind_contextvar(stack: ExitStack, var: ContextVar, value: Any) -> None:
    """Set `var` to `value` and register its reset on the stack.

    Keeps ContextVar set/reset symmetric and exception-safe across the run.
    """
    token = var.set(value)
    stack.callback(var.reset, token)


def _resolve_context_dependencies(
    ui, tool_confirmation, yolo, approval_channel, hook_manager
):
    # lazy: circular — runner → setup → runner (current_* ContextVars live in
    # runner.py, which imports this module at top level).
    from zrb.llm.agent.run.runner import (
        current_tool_confirmation,
        current_ui,
        current_yolo,
    )

    # lazy: zrb.llm.ui.* and zrb.llm.approval.* are imported inside this
    # function to break a circular import — zrb.llm.agent is loaded by
    # those packages' init paths, so module-top imports here would re-enter
    # zrb.llm.agent before its __init__ has finished.
    # lazy: zrb internal (heavy via transitive / circular)
    from zrb.llm.ui.std_ui import StdUI

    ui_arg = ui if ui is not None else current_ui.get()
    if ui_arg is None:
        ui_arg = StdUI()

    if isinstance(ui_arg, list):
        if len(ui_arg) == 1:
            effective_ui = ui_arg[0]
        elif len(ui_arg) == 0:
            effective_ui = StdUI()
        else:
            # lazy: zrb internal (heavy via transitive / circular)
            from zrb.llm.ui.multi_ui import MultiUI

            effective_ui = MultiUI(ui_arg)
    else:
        effective_ui = ui_arg

    effective_tool_confirmation = tool_confirmation or current_tool_confirmation.get()
    effective_hook_manager = hook_manager or default_hook_manager
    effective_yolo = yolo or current_yolo.get()
    effective_approval_channel = approval_channel or current_approval_channel.get()

    if effective_approval_channel is not None and effective_ui is not None:
        # lazy: zrb internal (heavy via transitive / circular)
        from zrb.llm.approval.multiplex_approval_channel import (
            MultiplexApprovalChannel,
        )

        # lazy: zrb internal (heavy via transitive / circular)
        from zrb.llm.approval.terminal_approval_channel import TerminalApprovalChannel

        if not isinstance(effective_approval_channel, MultiplexApprovalChannel):
            ui_for_terminal = effective_ui
            children = getattr(effective_ui, "children", None)
            if children:
                ui_for_terminal = children[0]
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


def _log_startup(
    tool_confirmation,
    effective_tool_confirmation,
    approval_channel,
    effective_approval_channel,
):
    # lazy: circular — runner → setup → runner (current_* ContextVars live in
    # runner.py, which imports this module at top level).
    from zrb.llm.agent.run.runner import current_tool_confirmation

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


def _setup_print_and_events(print_fn, event_handler, effective_ui):
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
        )
    return effective_print_fn, effective_event_handler
