"""Driving an interactive chat session through the UI it assembles.

The one-shot path (`task/chat/running.py`, `run_non_interactive_session`) needs
no UI: it reads the UIs already attached and runs the inner task once. An
interactive session is the other shape — it builds a UI from the task's own
values, replays the stored conversation onto it, runs its loop and reads its
display back — so it lives beside the backends it chooses between. The task
asks `shared/session_presentation.py` for it rather than importing `ui/`.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any, cast

from zrb.llm.orchestration.custom_command.resolver import (
    resolve_custom_commands,
    run_custom_command,
)
from zrb.llm.contracts.shared.feature_config import bound_session_ui
from zrb.llm.presentation.ui.assembly import assemble_ui
from zrb.util.attr import get_attr
from zrb.util.cli.style import stylize_muted

if TYPE_CHECKING:
    from zrb.context.any_context import AnyContext
    from zrb.llm.engine.agent.types import UserContent
    from zrb.llm.orchestration.custom_command.any_custom_command import AnyCustomCommand
    from zrb.llm.capabilities.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.orchestration.task.chat.task import LLMChatTask
    from zrb.llm.orchestration.task.llm_task import LLMTask
    from zrb.llm.presentation.ui.any_ui import AnyUI
    from zrb.llm.presentation.ui.base.ui import BaseUI


async def run_interactive_session(
    llm_chat_task: "LLMChatTask",
    *,
    ctx: "AnyContext",
    llm_task_core: "LLMTask",
    history_manager: "AnyHistoryManager",
    ui_commands: dict[str, list[str]],
    initial_message: str | None,
    initial_conversation_name: str,
    initial_yolo: "bool | frozenset[str]",
    initial_attachments: "list[UserContent]",
    enable_rewind: bool = False,
    snapshot_dir: str = "",
) -> object:
    """Run *llm_chat_task*'s session through the UI assembled for it.

    Returns the UI's last output, which is what the command line exits with.
    """
    # lazy: circular — `task/chat/execution.py` imports `ui/fallback/resolution`
    # for `resolve_ui`, so a module-level import back into `task/` closes the
    # package cycle (test_circular_import_allowlist.py). Both helpers are
    # needed once per session, not when this module loads.
    from zrb.llm.orchestration.task.chat.message_expansion import expand_message, is_action_command
    from zrb.llm.orchestration.task.chat.persistence import replay_conversation

    resolved_custom_commands = resolve_custom_commands(llm_chat_task.custom_commands)
    # An action may need the UI (`/photo` attaches to it), which does not
    # exist yet: run it once the UI does.
    initial_action = ""
    if is_action_command(initial_message, resolved_custom_commands):
        initial_action, initial_message, reply = initial_message, "", None
    else:
        initial_message, reply = expand_message(
            initial_message, resolved_custom_commands
        )
    if initial_message is None:
        initial_message = ""

    resolved_uis: list["AnyUI"] = list(llm_chat_task.uis)
    for factory in llm_chat_task.ui_factories:
        factory_ui = factory(
            ctx=ctx,
            llm_task=llm_task_core,
            history_manager=history_manager,
            ui_commands=ui_commands,
            initial_message=initial_message,
            initial_conversation_name=initial_conversation_name,
            initial_yolo=initial_yolo,
            initial_attachments=initial_attachments,
            custom_commands=resolved_custom_commands,
        )
        if isinstance(factory_ui, list):
            resolved_uis.extend(factory_ui)
        else:
            resolved_uis.append(factory_ui)

    default_ui_kwargs = _build_default_ui_kwargs(
        llm_chat_task,
        ctx=ctx,
        llm_task_core=llm_task_core,
        history_manager=history_manager,
        initial_message=initial_message,
        initial_conversation_name=initial_conversation_name,
        initial_yolo=initial_yolo,
        initial_attachments=initial_attachments,
        enable_rewind=enable_rewind,
        snapshot_dir=snapshot_dir,
        resolved_custom_commands=resolved_custom_commands,
    )

    ui = assemble_ui(
        uis=resolved_uis,
        default_kwargs=default_ui_kwargs,
        include_default_ui=llm_chat_task.include_default_ui,
        approval_channels=llm_chat_task.approval_channels,
    )

    if initial_conversation_name:
        replay_conversation(ui, history_manager, initial_conversation_name)
    if initial_action:
        outcome = run_custom_command(
            initial_action, resolved_custom_commands, _get_action_ui(ui)
        )
        reply = outcome.reply if outcome is not None else None
    if reply:
        ui.append_to_output(stylize_muted(f"\n  {reply}\n"))

    with bound_session_ui(_get_action_ui(ui)):
        await ui.run_async()
    last_output = ui.display.last_output
    final_conversation_name = llm_chat_task.get_ui_conversation_name(
        ui, initial_conversation_name
    )
    ctx.xcom["__conversation_name__"] = final_conversation_name
    return last_output


def _build_default_ui_kwargs(
    llm_chat_task: "LLMChatTask",
    *,
    ctx: "AnyContext",
    llm_task_core: "LLMTask",
    history_manager: "AnyHistoryManager",
    initial_message: str | None,
    initial_conversation_name: str,
    initial_yolo: "bool | frozenset[str]",
    initial_attachments: "list[UserContent]",
    enable_rewind: bool = False,
    snapshot_dir: str = "",
    resolved_custom_commands: "list[AnyCustomCommand] | None" = None,
) -> dict[str, Any]:
    """Build keyword arguments shared by all default UI constructor calls."""
    resolved_custom_model_names = (
        get_attr(ctx, llm_chat_task.custom_model_names, []) or []
    )
    if not isinstance(resolved_custom_model_names, list):
        resolved_custom_model_names = []

    if resolved_custom_commands is None:
        resolved_custom_commands = resolve_custom_commands(
            llm_chat_task.custom_commands
        )

    # Layer this run's yolo state and session name over the task's ui_config.
    ui_config = replace(
        llm_chat_task.ui_config,
        is_yolo=initial_yolo,
        conversation_session_name=initial_conversation_name,
    )

    return {
        "ctx": ctx,
        "output_lexer": None,  # resolved lazily to avoid early import
        "llm_task": llm_task_core,
        "history_manager": history_manager,
        "initial_message": initial_message,
        "initial_attachments": initial_attachments,
        "ui_config": ui_config,
        "triggers": llm_chat_task.triggers,
        "response_handlers": llm_chat_task.response_handlers,
        "tool_policies": llm_chat_task.tool_policies,
        "argument_formatters": llm_chat_task.argument_formatters,
        "markdown_theme": llm_chat_task.markdown_theme,
        "custom_commands": resolved_custom_commands,
        "model": llm_chat_task.get_model(ctx),
        "custom_model_names": resolved_custom_model_names,
        "enable_rewind": enable_rewind,
        "snapshot_dir": snapshot_dir,
    }


def _get_action_ui(ui: "AnyUI") -> "BaseUI":
    """The UI an action command acts on: a `MultiUI`'s main UI, else *ui*."""
    return cast("BaseUI", getattr(ui, "main_ui", None) or ui)
