"""
Minimal UI Example - Simplified with SimpleUI

This example demonstrates the SIMPLEST way to create a custom UI backend
using the new SimpleUI base class.

══════════════════════════════════════════════════════════════════════════════
BEFORE (BaseUI):                    AFTER (SimpleUI):
══════════════════════════════════════════════════════════════════════════════
- 180 lines                        → 40 lines
- 25+ constructor params           → 2 methods to implement
- Complex run_async()              → Just print() and get_input()
- Factory with 8 params            → Factory in 1 line

══════════════════════════════════════════════════════════════════════════════

Usage:
    zrb llm chat                        # Start chat with minimal UI
    zrb llm chat --message "Hello"     # Start with initial message
    ZRB_CHAT_LOG_FILE=chat.log zrb llm chat  # Log to file

Extension Levels:
    ┌─────────────────────────────────────────────────────────────────┐
    │ Level 0: UIProtocol (minimal, 4 methods)                        │
    │         - For tool confirmations only                           │
    ├─────────────────────────────────────────────────────────────────┤
    │ Level 1: SimpleUI (THIS EXAMPLE - simplest)                     │
    │         - Implement 2 methods: print(), get_input()             │
    │         - For basic backends (CLI, simple WebSocket)            │
    ├─────────────────────────────────────────────────────────────────┤
    │ Level 2: EventDrivenUI (event-driven)                           │
    │         - Implement: print(), start_event_loop()                │
    │         - Call handle_incoming_message() on events              │
    │         - For Telegram, Discord, WhatsApp                       │
    ├─────────────────────────────────────────────────────────────────┤
    │ Level 3: PollingUI (polling-based)                              │
    │         - Implement: print()                                    │
    │         - Use output_queue / input_queue                        │
    │         - For HTTP API, WebSocket polling                       │
    └─────────────────────────────────────────────────────────────────┘
"""

import asyncio
import os

from zrb.builtin.llm.chat import llm_chat
from zrb.llm.app.ui import SimpleUI, create_ui_factory

# =============================================================================
# Configuration (optional)
# =============================================================================

LOG_FILE = os.environ.get("ZRB_CHAT_LOG_FILE", None)


# =============================================================================
# MinimalUI - Just 2 methods to implement!
# =============================================================================


class MinimalUI(SimpleUI):
    """The simplest possible UI - just implement print() and get_input()."""

    def __init__(self, log_file: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._log_file = log_file

    async def print(self, text: str) -> None:
        """Display output to user.

        Note: This MUST be async because SimpleUI.append_to_output()
        uses asyncio.create_task() to schedule this method.
        """
        print(text, end="", flush=True)

        # Optional: Log to file
        if self._log_file:
            try:
                with open(self._log_file, "a", encoding="utf-8") as f:
                    f.write(text)
            except Exception:
                pass

    async def get_input(self, prompt: str) -> str:
        """Get user input asynchronously."""
        if prompt:
            print(prompt, end="", flush=True)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, input, "You> ")


# =============================================================================
# Integration with zrb - Just 1 line!
# =============================================================================

# The simplest way: use create_ui_factory
llm_chat.set_ui_factory(create_ui_factory(MinimalUI, log_file=LOG_FILE))

# That's it! When user runs `zrb llm chat`, it uses MinimalUI.
# No need to handle the factory parameters - create_ui_factory does it for you.
