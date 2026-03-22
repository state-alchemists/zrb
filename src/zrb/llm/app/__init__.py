"""UI implementations for LLM Chat applications.

This module provides multiple levels of UI abstractions:

Extension Hierarchy:
    ┌─────────────────────────────────────────────────────────────────┐
    │ Level 0: UIProtocol (minimal, 4 methods)                        │
    │         - For tool confirmations only                          │
    │         - See: zrb.llm.tool_call.ui_protocol                    │
    ├─────────────────────────────────────────────────────────────────┤
    │ Level 1: BaseUI (base class for full implementations)          │
    │         - Implement 4 required methods + run_async()            │
    │         - For custom UI backends (Telegram, Discord, etc.)    │
    │         - See: BaseUI class below                              │
    ├─────────────────────────────────────────────────────────────────┤
    │ Level 2: UI (terminal implementation)                          │
    │         - Full TUI with prompt_toolkit                        │
    │         - See: UI class below                                   │
    └─────────────────────────────────────────────────────────────────┘

Usage:
    # Using BaseUI for custom implementations (Telegram, Discord, etc.)
    from zrb.llm.app import BaseUI

    class MyUI(BaseUI):
        def append_to_output(self, *values, sep=" ", end="\\n", **kwargs):
            # Custom output logic (send to Telegram, Discord, etc.)
            ...

        async def ask_user(self, prompt: str) -> str:
            # Custom input logic (wait for Telegram message, etc.)
            ...

        async def run_interactive_command(self, cmd, shell=False):
            # Optional: execute shell commands or return None
            ...

        async def run_async(self) -> str:
            # Main event loop (start bot polling, etc.)
            ...

    # See examples/chat-telegram/ for a complete example.
"""

from zrb.llm.app.base_ui import BaseUI
from zrb.llm.app.ui import UI

__all__ = [
    "BaseUI",
    "UI",
]
