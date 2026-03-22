"""UI implementations for LLM Chat applications.

This module provides multiple levels of UI abstractions:

Extension Hierarchy:
    ┌─────────────────────────────────────────────────────────────────┐
    │ Level 0: UIProtocol (minimal, 4 methods)                        │
    │         - For tool confirmations only                          │
    │         - See: zrb.llm.tool_call.ui_protocol                    │
    ├─────────────────────────────────────────────────────────────────┤
    │ Level 1: SimpleUI (RECOMMENDED for beginners)                  │
    │         - Implement just 2 methods: print(), get_input()       │
    │         - For basic backends (CLI, simple WebSocket)          │
    │         - See: SimpleUI class below                             │
    ├─────────────────────────────────────────────────────────────────┤
    │ Level 2: EventDrivenUI (for event-driven backends)             │
    │         - Implement: print(), start_event_loop()               │
    │         - Call handle_incoming_message() on events             │
    │         - For Telegram, Discord, WhatsApp                      │
    │         - See: EventDrivenUI class below                        │
    ├─────────────────────────────────────────────────────────────────┤
    │ Level 3: PollingUI (for polling backends)                      │
    │         - Implement: print()                                     │
    │         - Use built-in output_queue/input_queue                │
    │         - For HTTP API, WebSocket polling                      │
    │         - See: PollingUI class below                             │
    ├─────────────────────────────────────────────────────────────────┤
    │ Level 4: BaseUI (full control, advanced)                       │
    │         - Implement 5+ methods                                   │
    │         - For maximum flexibility                              │
    │         - See: BaseUI class below                              │
    ├─────────────────────────────────────────────────────────────────┤
    │ Level 5: UI (terminal implementation)                          │
    │         - Full TUI with prompt_toolkit                        │
    │         - See: UI class below                                   │
    └─────────────────────────────────────────────────────────────────┘

Quick Start:
    # SIMPLEST: Use SimpleUI with just 2 methods!
    from zrb.llm.app import SimpleUI, create_ui_factory
    from zrb.builtin.llm.chat import llm_chat

    class MyUI(SimpleUI):
        def print(self, text: str) -> None:
            print(text, end="")

        async def get_input(self, prompt: str) -> str:
            return await asyncio.to_thread(input, prompt or "You> ")

    llm_chat.set_ui_factory(create_ui_factory(MyUI))

    # See examples/chat-minimal-ui/ for a complete example.

Event-Driven (Telegram/Discord):
    from zrb.llm.app import EventDrivenUI, create_ui_factory

    class TelegramUI(EventDrivenUI):
        async def print(self, text: str) -> None:
            await self.bot.send_message(self.chat_id, text)

        async def start_event_loop(self) -> None:
            self.bot.add_handler(MessageHandler(filters.TEXT, self._on_message))

        async def _on_message(self, update, context):
            self.handle_incoming_message(update.message.text)  # Auto-routes!

    llm_chat.set_ui_factory(create_ui_factory(TelegramUI, bot=bot, chat_id=ID))

    # See examples/chat-telegram/ for a complete example.
"""

from zrb.llm.app.base_ui import BaseUI
from zrb.llm.app.simple_ui import (
    EventDrivenUI,
    PollingUI,
    SimpleUI,
    UIConfig,
    create_ui_factory,
)
from zrb.llm.app.ui import UI

__all__ = [
    # Simple API (RECOMMENDED)
    "SimpleUI",
    "EventDrivenUI",
    "PollingUI",
    "UIConfig",
    "create_ui_factory",
    # Advanced API
    "BaseUI",
    "UI",
]
