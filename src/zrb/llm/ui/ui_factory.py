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
    ui_config: UIConfig | None = None,
    **extra_kwargs,
) -> Callable:
    """Wrap a UI class as an `llm_chat.ui_factories` entry.

    `LLMChatTask` calls a factory with eight positional-by-name arguments once
    the run's context exists; this adapts that call to the `ui_config`-shaped
    constructor every UI in `zrb.llm.ui` takes, so registering a custom backend
    is one line instead of a hand-written eight-parameter shim.

    Args:
        ui_class: A `SimpleUI`, `EventDrivenUI` or `BaseUI` subclass — the
            three documented extension levels, each pinned by
            `test/llm/ui/test_extension_levels.py`. Anything else whose
            `__init__` accepts `ctx`, `llm_task`, `history_manager`,
            `ui_config`, `initial_message`, `initial_attachments` and
            `custom_commands` works too. `MultiUI` and `BufferedUI` do not:
            they wrap other UIs and take `uis`/`wrapped_ui` instead.
        ui_config: Optional `UIConfig`. Copied before this run's yolo state and
            session name are stamped on, so one config object is safe to share
            across repeated factory invocations.
        **extra_kwargs: Passed to `ui_class` unchanged, for a subclass with
            constructor arguments of its own.

    Returns:
        A factory function compatible with `llm_chat.ui_factories`.

    Example:
        from zrb.llm.ui import create_ui_factory, UIConfig

        llm_chat.ui_factories = [
            create_ui_factory(
                MyUI, ui_config=UIConfig(assistant_name="MyBot"), bot=my_bot
            )
        ]
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
        cfg = ui_config or UIConfig.default()
        if ui_commands:
            cfg = cfg.merge_commands(ui_commands)
        else:
            # Always copy before mutating below — `ui_config` may be a single
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
            ui_config=cfg,
            initial_message=initial_message,
            initial_attachments=initial_attachments,
            custom_commands=custom_commands,
            **extra_kwargs,
        )

    return factory
