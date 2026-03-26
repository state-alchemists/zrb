from typing import Any as AnyType
from typing import Callable

from zrb.llm.app.ui.base_ui import BaseUI
from zrb.llm.app.ui.config import UIConfig


def create_ui_factory(
    ui_class: type,
    config: UIConfig | None = None,
    **extra_kwargs,
) -> Callable:
    from zrb.context.any_context import AnyContext
    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.task.llm_task import LLMTask

    def factory(
        ctx: AnyContext,
        llm_task_core: LLMTask,
        history_manager: AnyHistoryManager,
        ui_commands: dict[str, list[str]],
        initial_message: str,
        initial_conversation_name: str,
        initial_yolo: bool,
        initial_attachments: list[AnyType],
    ) -> BaseUI:
        cfg = config or UIConfig.default()
        if ui_commands:
            cfg = cfg.merge_commands(ui_commands)
        cfg.yolo = initial_yolo
        cfg.conversation_session_name = initial_conversation_name
        return ui_class(
            ctx=ctx,
            llm_task=llm_task_core,
            history_manager=history_manager,
            config=cfg,
            initial_message=initial_message,
            initial_attachments=initial_attachments,
            **extra_kwargs,
        )

    return factory
