"""UI implementations for LLM Chat applications.

This module provides multiple levels of UI abstractions for different use cases.

═════════════════════════════════════════════════════════════════════════════
UI CLASS HIERARCHY
═════════════════════════════════════════════════════════════════════════════

The UI system is organized into levels based on complexity and use case:

    ┌────────────────────────────────────────────────────────────────────────┐
    │ Protocol Level (minimal interface)                                     │
    ├────────────────────────────────────────────────────────────────────────┤
    │ UIProtocol (zrb.llm.tool_call.ui_protocol)                             │
    │   - 4 methods: ask_user, append_to_output, stream_to_parent,           │
    │                 run_interactive_command                                │
    │   - Used for tool confirmations in non-chat contexts                   │
    │   - Implemented by: StdUI (zrb.llm.ui.std_ui)                          │
    ├────────────────────────────────────────────────────────────────────────┤
    │ Chat UI Levels (for LLM chat applications)                             │
    ├────────────────────────────────────────────────────────────────────────┤
    │ Level 1: SimpleUI (RECOMMENDED for beginners)                          │
    │   - Implement: print(), get_input() (2 methods)                        │
    │   - Best for: CLI, file logging, simple backends                       │
    │   - Auto-handles: message loop, command processing                     │
    │                                                                        │
    │ Level 2: EventDrivenUI                                                 │
    │   - Implement: print(), start_event_loop()                             │
    │   - Best for: Telegram, Discord, WhatsApp (callback-based)             │
    │   - Provides: input queue, handle_incoming_message() routing           │
    │                                                                        │
    │ Level 3: PollingUI                                                     │
    │   - Implement: print() (optional)                                      │
    │   - Best for: HTTP API, WebSocket polling                              │
    │   - Provides: built-in input_queue, output_queue                       │
    │                                                                        │
    │ Level 4: BaseUI                                                        │
    │   - Implement: __init__, append_to_output(), ask_user(),               │
    │               run_interactive_command(), run_async()                   │
    │   - Best for: Maximum flexibility, custom architectures                │
    │                                                                        │
    │ Level 5: UI (default terminal)                                         │
    │   - Full-featured TUI with prompt_toolkit                              │
    │   - Used when no custom UI is configured                               │
    └────────────────────────────────────────────────────────────────────────┘

DUAL MODE (CLI + External Channel)
═════════════════════════════════════════════════════════════════════════════

For chat applications that work with both CLI and an external channel
(Telegram, SSE, WebSocket), use append_ui_factory() to add channels:

    # Add Telegram alongside default CLI
    llm_chat.append_ui_factory(create_ui_factory(TelegramUI, bot=bot, chat_id=ID))

    # Add SSE alongside default CLI
    llm_chat.append_ui_factory(create_ui_factory(SSEUI, server=server))

The framework automatically creates MultiUI which:
- Broadcasts output to ALL configured channels
- Waits for input from ANY channel (first response wins)

See examples/chat-telegram/ and examples/chat-sse/ for complete implementations.

QUICK START
═════════════════════════════════════════════════════════════════════════════

Single Channel (CLI only):
    from zrb.llm.ui import SimpleUI, create_ui_factory
    from zrb.builtin.llm.chat import llm_chat

    class MyUI(SimpleUI):
        async def print(self, text: str, kind: str = "text") -> None:
            print(text, end="")

        async def get_input(self, prompt: str) -> str:
            return await asyncio.to_thread(input, prompt or "You> ")

    # Define custom factory to receive llm_task parameter
    def my_factory(ctx, llm_task, history_manager, ui_commands,
                   initial_message, initial_conversation_name,
                   initial_yolo, initial_attachments):
        from zrb.llm.ui import UIConfig
        config = UIConfig.default()
        return MyUI(
            ctx=ctx,
            llm_task=llm_task,
            history_manager=history_manager,
            config=config,
            initial_message=initial_message,
            initial_attachments=initial_attachments,
        )

    llm_chat.set_ui_factory(my_factory)

    # Or use create_ui_factory helper (recommended)
    llm_chat.set_ui_factory(create_ui_factory(MyUI))

    # See examples/chat-minimal-ui/

Dual Mode (CLI + Telegram):
    from zrb.llm.ui import EventDrivenUI, create_ui_factory
    from zrb.builtin.llm.chat import llm_chat

    class TelegramUI(EventDrivenUI):
        async def print(self, text: str, kind: str = "text") -> None:
            await self.bot.send_message(self.chat_id, text)

        async def start_event_loop(self) -> None:
            # Start bot and register handlers
            ...

    # Use create_ui_factory helper (recommended)
    llm_chat.append_ui_factory(create_ui_factory(TelegramUI, bot=bot, chat_id=ID))

    # See examples/chat-telegram/
"""

from zrb.llm.ui.base.ui import BaseUI
from zrb.llm.ui.default.ui import UI
from zrb.llm.ui.multi_ui import MultiUI
from zrb.llm.ui.buffered_output_mixin import BufferedOutputMixin
from zrb.llm.ui.event_driven_ui import EventDrivenUI
from zrb.llm.ui.polling_ui import PollingUI
from zrb.llm.ui.simple_ui_base import SimpleUI
from zrb.llm.ui.ui_config import UIConfig
from zrb.llm.ui.ui_factory import (
    create_bot_ui_factory,
    create_http_ui_factory,
    create_ui_factory,
)

__all__ = [
    "BufferedOutputMixin",
    # Simple API (RECOMMENDED)
    "SimpleUI",
    "EventDrivenUI",
    "PollingUI",
    "UIConfig",
    "create_ui_factory",
    # Factory helpers for common patterns
    "create_bot_ui_factory",
    "create_http_ui_factory",
    # Advanced API
    "BaseUI",
    "UI",
    # Multi-channel support
    "MultiUI",
]
