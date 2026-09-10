"""Minimal custom chat UI, built on SimpleUI.

`SimpleUI` runs the message loop, slash-command dispatch and tool approvals;
a subclass supplies the two ends of the conversation — `print()` to show
output and `get_input()` to read a line. `create_ui_factory` wires the class
into the built-in `llm_chat` task, so `zrb llm chat` uses it in place of the
default terminal UI.

Usage:
    zrb llm chat                              # Start chat with this UI
    zrb llm chat --message "Hello"            # Start with an initial message
    ZRB_CHAT_LOG_FILE=chat.log zrb llm chat   # Also append output to a file

Which base class to subclass:

    AnyUI           The full UI contract. For tool confirmations outside a
                    chat loop; everything below implements it for you.
    SimpleUI        Implement print() and get_input(). For backends that
                    block waiting for a line — a CLI, a log, a simple socket.
                    Used here.
    EventDrivenUI   Implement print() and start_event_loop(), then call
                    handle_incoming_message() as messages arrive. For
                    Telegram, Discord, HTTP and WebSocket backends.
    BaseUI          Nothing is required; override what you want to change.
                    For a UI whose structure differs from both loops above.

`docs/llm/llm-custom-ui.md` covers each level in full.
"""

import asyncio
import os

from zrb.builtin.llm.chat import llm_chat
from zrb.llm.ui import SimpleUI, create_ui_factory

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

    async def print(self, text: str, kind: str = "text") -> None:
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
llm_chat.ui_factories = [create_ui_factory(MinimalUI, log_file=LOG_FILE)]

# That's it! When user runs `zrb llm chat`, it uses MinimalUI.
# No need to handle the factory parameters - create_ui_factory does it for you.
