from typing import Any, Callable

from zrb.llm.ui.ui_config import UIConfig


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
        A factory function compatible with llm_chat.set_ui_factory()

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
                # ... 10+ more lines
            )

        # After (one liner):
        from zrb.llm.ui import create_ui_factory, UIConfig

        config = UIConfig(assistant_name="MyBot")
        llm_chat.set_ui_factory(create_ui_factory(MyUI, config=config, bot=my_bot))
    """
    from zrb.context.any_context import AnyContext
    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.task.llm_task import LLMTask
    from zrb.llm.ui.base.ui import BaseUI

    def factory(
        ctx: AnyContext,
        llm_task: LLMTask,
        history_manager: AnyHistoryManager,
        ui_commands: dict[str, list[str]],
        initial_message: str,
        initial_conversation_name: str,
        initial_yolo: bool,
        initial_attachments: list[Any],
    ) -> BaseUI:
        # Create config with merged commands
        cfg = config or UIConfig.default()
        if ui_commands:
            cfg = cfg.merge_commands(ui_commands)

        # Set yolo and conversation name from parameters
        cfg.is_yolo = initial_yolo
        cfg.conversation_session_name = initial_conversation_name

        return ui_class(
            ctx=ctx,
            llm_task=llm_task,
            history_manager=history_manager,
            config=cfg,
            initial_message=initial_message,
            initial_attachments=initial_attachments,
            **extra_kwargs,
        )

    return factory


def create_bot_ui_factory(
    ui_class: type,
    config: UIConfig | None = None,
    **bot_kwargs,
) -> Callable:
    """Create a UI factory for bot-based backends (Telegram, Discord, etc.).

    This is a convenience wrapper around create_ui_factory that handles
    common bot backend patterns.

    Args:
        ui_class: Your EventDrivenUI subclass
        config: Optional UIConfig
        **bot_kwargs: Bot-specific parameters (token, chat_id, etc.)

    Returns:
        A factory function for use with llm_chat.append_ui_factory()

    Example:
        from zrb.llm.ui import EventDrivenUI, create_bot_ui_factory
        from zrb.builtin.llm.chat import llm_chat

        class TelegramUI(EventDrivenUI):
            def __init__(self, bot_token, chat_id, **kwargs):
                super().__init__(**kwargs)
                self.bot_token = bot_token
                self.chat_id = chat_id

            async def print(self, text: str, kind: str = "text") -> None:
                await self.bot.send_message(self.chat_id, text)

            async def start_event_loop(self) -> None:
                # Initialize bot
                ...

        # Single line registration!
        llm_chat.append_ui_factory(
            create_bot_ui_factory(
                TelegramUI,
                bot_token="TOKEN",
                chat_id=12345
            )
        )
    """
    return create_ui_factory(ui_class, config=config, **bot_kwargs)


def create_http_ui_factory(
    ui_class: type,
    config: UIConfig | None = None,
    host: str = "localhost",
    port: int = 8000,
    **server_kwargs,
) -> Callable:
    """Create a UI factory for HTTP-based backends (SSE, WebSocket, REST API).

    This is a convenience wrapper around create_ui_factory that handles
    common HTTP server patterns.

    Args:
        ui_class: Your PollingUI or EventDrivenUI subclass
        config: Optional UIConfig
        host: Server bind address
        port: Server port
        **server_kwargs: Server-specific parameters

    Returns:
        A factory function for use with llm_chat.append_ui_factory()

    Example:
        from zrb.llm.ui import EventDrivenUI, create_http_ui_factory
        from zrb.builtin.llm.chat import llm_chat
        from aiohttp import web

        class SSEUI(EventDrivenUI):
            def __init__(self, host, port, **kwargs):
                super().__init__(**kwargs)
                self.host = host
                self.port = port

            async def print(self, text: str, kind: str = "text") -> None:
                await self.broadcast(text, kind=kind)

            async def start_event_loop(self) -> None:
                app = web.Application()
                # Set up routes
                ...

        llm_chat.append_ui_factory(
            create_http_ui_factory(
                SSEUI,
                host="localhost",
                port=8000
            )
        )
    """
    return create_ui_factory(
        ui_class,
        config=config,
        host=host,
        port=port,
        **server_kwargs,
    )
