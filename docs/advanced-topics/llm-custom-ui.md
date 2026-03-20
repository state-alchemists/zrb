# LLM Custom UI and Approval Channels

Zrb's LLM tasks support custom UI and approval channels for non-terminal interfaces like Telegram, Slack, or web applications.

## Architecture

With the latest architectural improvements, you can inherit from `BaseUI` to create fully-featured custom UIs that retain all chat loop logic (command parsing, session management, message queues) while only replacing the I/O layer.

```text
┌─────────────────────────────────────────────────────────────┐
│                     LLMChatTask                              │
│                                                             │
│  ┌─────────────────┐         ┌─────────────────────┐       │
│  │   BaseUI        │         │  ApprovalChannel    │       │
│  │  (Inherit)      │         │                     │       │
│  │                 │         │ request_approval()  │       │
│  │  ask_user()     │         │ notify()            │       │
│  │  append_output()│         │                     │       │
│  │  stream_output()│         │                     │       │
│  └────────┬────────┘         └──────────┬──────────┘       │
│           │                             │                  │
│           │    set_ui_factory()  set_approval_channel()     │
│           └──────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

## Creating a Custom UI

To create a custom UI, inherit from `zrb.llm.app.base_ui.BaseUI` and implement the abstract I/O methods. This gives your custom UI access to the complete interactive chat loop.

```python
from typing import Any, TextIO
from zrb.llm.app.base_ui import BaseUI

class MyCustomUI(BaseUI):
    """Custom UI implementation."""

    def append_to_output(
        self, *values: object, sep: str = " ", end: str = "\n", file: TextIO | None = None, flush: bool = False
    ):
        """Render output to your custom interface."""
        msg = sep.join(str(v) for v in values) + end
        self._send_to_interface(msg)
        
    def stream_to_parent(
        self, *values: object, sep: str = " ", end: str = "\n", file: TextIO | None = None, flush: bool = False
    ):
        """Stream output immediately."""
        self.append_to_output(*values, sep=sep, end=end, file=file, flush=flush)

    async def ask_user(self, prompt: str) -> str:
        """Block and ask for input from your custom interface."""
        self._send_to_interface(f"❓ {prompt}")
        return await self._wait_for_input()

    async def run_interactive_command(self, cmd: str | list[str], shell: bool = False) -> Any:
        """Execute interactive command. (Usually disabled for remote UIs)"""
        self._send_to_interface(f"⚠️ Command execution disabled")
        return {"error": "Disabled"}
```

## ApprovalChannel

The `ApprovalChannel` handles tool call confirmations:

```python
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult

class ApprovalChannel(Protocol):
    async def request_approval(self, context: ApprovalContext) -> ApprovalResult: ...
    async def notify(self, message: str, context: ApprovalContext | None = None): ...
```

---

## Telegram Implementation Example

See `examples/telegram/zrb_init.py` for a complete working example of how to hijack the built-in `zrb chat` command to run over Telegram.

The example demonstrates:
1. Inheriting from `BaseUI` to handle Telegram I/O while keeping Zrb's chat commands (`/save`, `/load`, `/attach`, etc.) working seamlessly.
2. Implementing `TelegramApprovalChannel` using Telegram's Inline Keyboard Buttons for interactive tool approvals.
3. Using `set_ui_factory()` to inject the custom UI with the required runtime context dynamically.

---

## Notes

1. **Stripping ANSI Codes**: Remote UIs often do not support terminal ANSI color codes. Use `zrb.util.cli.style.remove_style(text)` to strip these codes before sending text to your remote interface.
2. **`interactive=False` Legacy**: Previously, custom UIs required running the task in non-interactive mode. By inheriting from `BaseUI`, your custom UI *is* the interactive loop.
3. **Timeouts**: Always implement timeouts for remote channels in `ask_user` and `request_approval` to prevent the agent from hanging indefinitely if the remote service drops the connection or the user stops responding.