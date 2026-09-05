from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, Callable

from zrb.context.any_context import AnyContext
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.ui.base.ui import BaseUI
from zrb.llm.ui.ui_config import UIConfig

if TYPE_CHECKING:
    from zrb.llm.task.llm_task import LLMTask


def create_ui_factory(
    ui_class: type,
    config: UIConfig | None = None,
    **extra_kwargs,
) -> Callable:
    """Create a UI factory function with minimal boilerplate.

    This replaces the repetitive 8-parameter factory function with
    a one-liner.

    Args:
        ui_class: The UI class to instantiate
        config: Optional UIConfig for custom commands
        **extra_kwargs: Additional kwargs passed to the constructor

    Returns:
        A factory function compatible with llm_chat.ui_factories

    Example:
        # Before (repetitive):
        def create_ui(ctx, llm_task_core, history_manager, ui_commands,
                      initial_message, initial_conversation_name,
                      initial_yolo, initial_attachments):
            return MyUI(
                ctx=ctx, llm_task=llm_task_core, history_manager=history_manager,
                initial_message=initial_message,
                conversation_session_name=initial_conversation_name,
                is_yolo=initial_yolo, initial_attachments=initial_attachments,
                exit_commands=ui_commands.get("exit", ["/exit"]),
            )

        # After (one liner):
        from zrb.llm.ui import create_ui_factory, UIConfig

        config = UIConfig(assistant_name="MyBot")
        llm_chat.ui_factories = [create_ui_factory(MyUI, config=config, bot=my_bot)]
    """

    def factory(
        ctx: AnyContext,
        llm_task: LLMTask,
        history_manager: AnyHistoryManager,
        ui_commands: dict[str, list[str]],
        initial_message: str,
        initial_conversation_name: str,
        initial_yolo: bool,
        initial_attachments: list[Any],
        custom_commands: list[Any] | None = None,
    ) -> BaseUI:
        cfg = config or UIConfig.default()
        if ui_commands:
            cfg = cfg.merge_commands(ui_commands)
        else:
            # Always copy before mutating below — `config` may be a single
            # object shared across repeated factory invocations (e.g. a
            # long-lived bot serving multiple chats), and mutating it in
            # place would leak one chat's yolo/session-name state into the
            # next. `merge_commands` above already returns a fresh copy.
            cfg = dataclasses.replace(cfg)

        cfg.is_yolo = initial_yolo
        cfg.conversation_session_name = initial_conversation_name

        return ui_class(
            ctx=ctx,
            llm_task=llm_task,
            history_manager=history_manager,
            config=cfg,
            initial_message=initial_message,
            initial_attachments=initial_attachments,
            custom_commands=custom_commands,
            **extra_kwargs,
        )

    return factory
