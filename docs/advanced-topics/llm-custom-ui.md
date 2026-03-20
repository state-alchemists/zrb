# LLM Custom UI and Approval Channels

Zrb's LLM tasks support custom UI and approval channels for non-terminal interfaces like Telegram, Slack, or web applications.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     LLMChatTask                              │
│                   (interactive=False)                        │
│                                                             │
│  ┌─────────────────┐         ┌─────────────────────┐       │
│  │   UIProtocol    │         │  ApprovalChannel    │       │
│  │                 │         │                     │       │
│  │  ask_user()     │         │ request_approval()  │       │
│  │  append_output()│         │ notify()            │       │
│  │  stream_output()│         │                     │       │
│  └────────┬────────┘         └──────────┬──────────┘       │
│           │                             │                  │
│           │    set_ui()      set_approval_channel()         │
│           └──────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

## UIProtocol

The `UIProtocol` defines how the agent interacts with users:

```python
from zrb.llm.tool_call.ui_protocol import UIProtocol

class UIProtocol(Protocol):
    async def ask_user(self, prompt: str) -> str: ...
    def append_to_output(self, *values, sep=" ", end="\n", file=None, flush=False): ...
    def stream_to_parent(self, *values, sep=" ", end="\n", file=None, flush=False): ...
    async def run_interactive_command(self, cmd: str | list[str], shell: bool = False) -> Any: ...
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

## Built-in Channels

| Channel | Purpose |
|---------|---------|
| `NullApprovalChannel` | Auto-approve everything (YOLO mode) |
| `TerminalApprovalChannel` | CLI-based approval prompts |

---

## Telegram Implementation

Complete implementation for running an LLM agent via Telegram:

### TelegramUI

```python
import asyncio
from typing import Any
from zrb.llm.tool_call.ui_protocol import UIProtocol


class TelegramUI(UIProtocol):
    """UIProtocol implementation for Telegram."""

    def __init__(self, bot_token: str, chat_id: str, timeout: int = 300):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout = timeout
        self._bot = None
        self._application = None
        self._pending: dict[str, asyncio.Future[str]] = {}

    async def _ensure_bot(self):
        """Lazy init Telegram bot."""
        if self._bot:
            return
        from telegram.ext import Application, MessageHandler, filters

        self._application = Application.builder().token(self.bot_token).build()
        self._application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )
        await self._application.initialize()
        await self._application.start()
        await self._application.updater.start_polling()
        self._bot = self._application.bot

    async def _handle_message(self, update, context):
        """Route incoming messages to pending questions."""
        text = update.message.text
        for qid, future in list(self._pending.items()):
            if not future.done():
                future.set_result(text)
                self._pending.pop(qid, None)
                return

    async def ask_user(self, prompt: str) -> str:
        """Send question, wait for response."""
        await self._ensure_bot()
        await self._bot.send_message(chat_id=self.chat_id, text=f"❓ {prompt}")

        loop = asyncio.get_event_loop()
        future: asyncio.Future[str] = loop.create_future()
        self._pending[f"q_{id(future)}"] = future

        try:
            async with asyncio.timeout(self.timeout):
                return await future
        except asyncio.TimeoutError:
            self._pending.clear()
            await self._bot.send_message(chat_id=self.chat_id, text="⏰ Timed out")
            return ""

    def append_to_output(self, *values, sep=" ", end="\n", file=None, flush=False):
        """Buffer output (call flush_output to send)."""
        self._buffer = getattr(self, "_buffer", [])
        self._buffer.append(sep.join(str(v) for v in values) + end)

    def stream_to_parent(self, *values, sep=" ", end="\n", file=None, flush=False):
        """Send output immediately."""
        msg = sep.join(str(v) for v in values) + end
        asyncio.create_task(self._send(msg))

    async def _send(self, msg: str):
        await self._ensure_bot()
        if len(msg) > 4000:
            msg = msg[:3997] + "..."
        await self._bot.send_message(chat_id=self.chat_id, text=msg)

    async def flush_output(self):
        """Send buffered output."""
        if buffer := getattr(self, "_buffer", []):
            self._buffer = []
            await self._send("".join(buffer))

    async def run_interactive_command(self, cmd: str | list[str], shell: bool = False) -> Any:
        """Disabled for security."""
        await self._send(f"⚠️ Command execution disabled: {cmd}")
        return {"error": "Disabled"}

    async def shutdown(self):
        """Cleanup."""
        if self._application:
            await self._application.updater.stop()
            await self._application.stop()
            await self._application.shutdown()
```

### TelegramApprovalChannel

```python
import asyncio
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult


class TelegramApprovalChannel(ApprovalChannel):
    """ApprovalChannel with inline keyboard buttons."""

    def __init__(self, bot_token: str, chat_id: str, timeout: int = 300):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout = timeout
        self._bot = None
        self._application = None
        self._pending: dict[str, asyncio.Future[ApprovalResult]] = {}

    async def _ensure_bot(self):
        """Lazy init Telegram bot."""
        if self._bot:
            return
        from telegram.ext import Application, CallbackQueryHandler

        self._application = Application.builder().token(self.bot_token).build()
        self._application.add_handler(CallbackQueryHandler(self._handle_callback))
        await self._application.initialize()
        await self._application.start()
        await self._application.updater.start_polling()
        self._bot = self._application.bot

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        """Send approval request with Approve/Deny buttons."""
        await self._ensure_bot()
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        text = self._format_message(context)
        keyboard = [[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve:{context.tool_call_id}"),
            InlineKeyboardButton("❌ Deny", callback_data=f"deny:{context.tool_call_id}"),
        ]]
        
        loop = asyncio.get_event_loop()
        future: asyncio.Future[ApprovalResult] = loop.create_future()
        self._pending[context.tool_call_id] = future

        try:
            await self._bot.send_message(
                chat_id=self.chat_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            async with asyncio.timeout(self.timeout):
                return await future
        except asyncio.TimeoutError:
            self._pending.pop(context.tool_call_id, None)
            return ApprovalResult(approved=False, message="Timeout")

    async def _handle_callback(self, update, context):
        """Handle inline button press."""
        query = update.callback_query
        await query.answer()
        
        action, tool_call_id = query.data.split(":", 1)
        if tool_call_id not in self._pending:
            await query.edit_message_text("⚠️ Expired")
            return

        approved = action == "approve"
        result = ApprovalResult(approved=approved)
        self._pending.pop(tool_call_id).set_result(result)
        
        emoji = "✅" if approved else "❌"
        await query.edit_message_text(f"{emoji} {tool_call_id}")

    def _format_message(self, ctx: ApprovalContext) -> str:
        import json
        args = json.dumps(ctx.tool_args, indent=2, default=str)
        return f"🔔 *Tool:* `{ctx.tool_name}`\n\n```{args}```"

    async def notify(self, message: str, context=None):
        """Send notification."""
        await self._ensure_bot()
        await self._bot.send_message(chat_id=self.chat_id, text=message)

    async def shutdown(self):
        """Cleanup."""
        if self._application:
            await self._application.updater.stop()
            await self._application.stop()
            await self._application.shutdown()
```

---

## Usage

```python
import asyncio
from zrb.llm.task.llm_chat_task import LLMChatTask


async def run_telegram_bot():
    bot_token = "YOUR_BOT_TOKEN"
    chat_id = "YOUR_CHAT_ID"
    
    # Create UI and approval channel
    ui = TelegramUI(bot_token, chat_id)
    approval = TelegramApprovalChannel(bot_token, chat_id)
    
    # Create task with interactive=False for non-terminal UI
    task = LLMChatTask(
        name="telegram_agent",
        system_prompt="You are a helpful assistant.",
        interactive=False,  # Required for non-terminal UI
    )
    
    # Set UI and approval channel
    task.set_ui(ui)
    task.set_approval_channel(approval)
    
    # Run task...
    from zrb.session.session import Session
    from zrb.context.shared_context import SharedContext
    
    shared_ctx = SharedContext(input={"message": "Hello!"}, print_fn=lambda *a, **k: None)
    session = Session(shared_ctx)
    result = await task.async_run(session)
    
    await ui.flush_output()  # Send any remaining output
    await ui.shutdown()
    await approval.shutdown()


if __name__ == "__main__":
    asyncio.run(run_telegram_bot())
```

---

## Notes

1. **`interactive=False`** - Required for non-terminal UIs (Telegram, Slack, web)
2. **`set_ui()` / `set_approval_channel()`** - Set via constructor or setter method
3. **Timeouts** - Always implement timeouts for remote channels
4. **Error handling** - Wrap remote calls in try/except with fallbacks