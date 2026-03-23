# LLM Custom UI and Approval Channels

Zrb's LLM tasks support custom UI and approval channels for non-terminal interfaces like Telegram, Slack, Discord, or web applications.

## Quick Start

The simplest way to create a custom UI:

```python
from zrb.builtin.llm.chat import llm_chat
from zrb.llm.app.simple_ui import SimpleUI

class MyUI(SimpleUI):
    async def print(self, text: str) -> None:
        print(text, end="", flush=True)

    async def get_input(self, prompt: str) -> str:
        return await asyncio.to_thread(input, prompt or "You> ")

llm_chat.set_ui_factory(
    lambda ctx, task, hm, **kw: MyUI(ctx=ctx, llm_task=task, history_manager=hm)
)
```

That's it! Just 2 methods: `print()` and `get_input()`.

---

## UI Extension Levels

Choose your starting point based on complexity:

| Level | Base Class | Methods to Implement | Use Case |
|-------|-------------|----------------------|----------|
| **1** | `SimpleUI` | `print()`, `get_input()` | CLI, basic backends |
| **2** | `EventDrivenUI` | `print()`, `start_event_loop()` | Telegram, Discord, WhatsApp |
| **3** | `PollingUI` | `print()` | HTTP API, WebSocket |
| **4** | `BaseUI` | 5+ methods | Full control, all features |

**Recommendation:** Start with `SimpleUI`. Only use `BaseUI` if you need fine-grained control.

---

## Level 1: SimpleUI (Recommended for Basic Backends)

`SimpleUI` is the easiest way to create a custom UI. You implement:

- `print(text: str)` - Display output to user (**async**)
- `get_input(prompt: str)` - Get user input (**async**)

### Example: CLI with Custom Prompt

```python
import asyncio
from zrb.builtin.llm.chat import llm_chat
from zrb.llm.app.simple_ui import SimpleUI

class CustomCLI(SimpleUI):
    """Custom CLI with styled prompt."""

    async def print(self, text: str) -> None:
        print(text, end="", flush=True)

    async def get_input(self, prompt: str) -> str:
        if prompt:
            print(f"❓ {prompt}")
        return await asyncio.to_thread(input, "👤 You> ")

# Register
llm_chat.set_ui_factory(
    lambda ctx, task, hm, **kw: CustomCLI(ctx=ctx, llm_task=task, history_manager=hm)
)
```

### Example: Log to File

```python
import asyncio
from zrb.builtin.llm.chat import llm_chat
from zrb.llm.app.simple_ui import SimpleUI

class LoggingUI(SimpleUI):
    """CLI that also logs to file."""

    def __init__(self, log_file: str = "chat.log", **kwargs):
        super().__init__(**kwargs)
        self.log_file = log_file

    async def print(self, text: str) -> None:
        print(text, end="", flush=True)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(text)

    async def get_input(self, prompt: str) -> str:
        if prompt:
            print(f"❓ {prompt}")
        return await asyncio.to_thread(input, "You> ")

# Register
llm_chat.set_ui_factory(
    lambda ctx, task, hm, **kw: LoggingUI(log_file="my_chat.log", ctx=ctx, llm_task=task, history_manager=hm)
)
```

---

## Level 2: EventDrivenUI (For Event-Driven Backends)

For backends that receive messages via handlers/callbacks (Telegram, Discord, WhatsApp), use `EventDrivenUI`.

You implement:
- `print(text: str)` - Send output to user (**async**)
- `start_event_loop()` - Register your handlers

And call `handle_incoming_message(text)` when messages arrive.

### Key Concept: Automatic Message Routing

`EventDrivenUI` automatically routes messages:

```python
# When your handler receives a message:
async def on_message(text):
    # This routes automatically:
    # - If waiting for input (ask_user) → goes to queue, unblocks it
    # - Otherwise → submits to LLM as new message
    self.handle_incoming_message(text)
```

### Example: Telegram Bot

```python
from telegram.ext import Application, MessageHandler, filters
from zrb.builtin.llm.chat import llm_chat
from zrb.llm.app.simple_ui import EventDrivenUI, create_ui_factory

class TelegramUI(EventDrivenUI):
    def __init__(self, bot_token: str, chat_id: str, **kwargs):
        super().__init__(**kwargs)
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._app = None

    async def print(self, text: str) -> None:
        if self._app:
            await self._app.bot.send_message(self.chat_id, text)

    async def start_event_loop(self) -> None:
        self._app = Application.builder().token(self.bot_token).build()

        async def handle(update, context):
            text = update.message.text
            self.handle_incoming_message(text)  # Auto-routes!

        self._app.add_handler(MessageHandler(filters.TEXT, handle))
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()
        
        # Keep running until cancelled
        while True:
            await asyncio.sleep(1)

# Register - ONE line!
llm_chat.set_ui_factory(
    create_ui_factory(TelegramUI, bot_token=TOKEN, chat_id=CHAT_ID)
)
```

### Example: Discord Bot

```python
import discord
from zrb.builtin.llm.chat import llm_chat
from zrb.llm.app.simple_ui import EventDrivenUI, create_ui_factory

class DiscordUI(EventDrivenUI):
    def __init__(self, token: str, channel_id: int, **kwargs):
        super().__init__(**kwargs)
        self.token = token
        self.channel_id = channel_id
        self._client = None

    async def print(self, text: str) -> None:
        if self._client:
            channel = self._client.get_channel(self.channel_id)
            if channel:
                # Discord has 2000 char limit
                for chunk in [text[i:i+1900] for i in range(0, len(text), 1900)]:
                    await channel.send(chunk)

    async def start_event_loop(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        self._client = discord.Client(intents=intents)

        @self._client.event
        async def on_message(message):
            if message.author.bot:
                return
            if message.channel.id != self.channel_id:
                return
            self.handle_incoming_message(message.content)

        await self._client.start(self.token)

# Register - ONE line!
llm_chat.set_ui_factory(
    create_ui_factory(DiscordUI, token=TOKEN, channel_id=CHANNEL_ID)
)
```

---

## Level 3: PollingUI (For HTTP API & WebSocket)

For backends where external systems poll for messages, use `PollingUI`.

`PollingUI` provides built-in queues:
- `output_queue` - Messages from AI (external system polls this)
- `input_queue` - Responses from user (external system puts to this)

### Example: HTTP API

```python
from aiohttp import web
from zrb.builtin.llm.chat import llm_chat
from zrb.llm.app.simple_ui import PollingUI
import uuid

sessions = {}

class HttpAPIUI(PollingUI):
    """HTTP API UI using PollingUI's queues."""
    # print() already queues to output_queue!
    # get_input() already blocks on input_queue!
    pass

async def handle_chat(request):
    data = await request.json()
    session_id = str(uuid.uuid4())[:8]

    ui = HttpAPIUI(
        ctx=...,
        llm_task=llm_chat,
        history_manager=...,
        initial_message=data.get("message", ""),
    )
    sessions[session_id] = ui
    asyncio.create_task(ui.run_async())

    return web.json_response({"session_id": session_id})

async def handle_poll(request):
    session_id = request.query.get("session")
    ui = sessions.get(session_id)
    if not ui:
        return web.json_response({"error": "Invalid session"}, status=404)

    messages = []
    while not ui.output_queue.empty():
        messages.append(await ui.output_queue.get())

    return web.json_response({"messages": messages})

async def handle_respond(request):
    data = await request.json()
    ui = sessions.get(data.get("session"))
    if ui:
        await ui.input_queue.put(data.get("text", ""))
    return web.json_response({"status": "ok"})
```

---

## BufferedOutputMixin (For Rate-Limited Backends)

For backends with rate limits (Telegram, Discord), use `BufferedOutputMixin` to batch output:

```python
from zrb.llm.app.simple_ui import EventDrivenUI, BufferedOutputMixin

class TelegramUI(EventDrivenUI, BufferedOutputMixin):
    def __init__(self, bot_token: str, chat_id: str, **kwargs):
        super().__init__(**kwargs)
        BufferedOutputMixin.__init__(self, flush_interval=0.3, max_buffer_size=3000)
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._app = None

    async def print(self, text: str) -> None:
        # Buffer output instead of sending immediately
        self.buffer_output(text)

    async def _send_buffered(self, text: str) -> None:
        """Called when buffer is flushed."""
        if self._app:
            await self._app.bot.send_message(self.chat_id, text)

    async def start_event_loop(self) -> None:
        # Start the bot
        self._app = Application.builder().token(self.bot_token).build()
        # ... register handlers ...
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()
        
        # Start flush loop and keep running
        await self.start_flush_loop()
        while True:
            await asyncio.sleep(1)
```

This prevents fragmented messages when the LLM streams tokens.

---

## UIConfig: Simplifying Configuration

Use `UIConfig` to bundle all command settings:

```python
from zrb.llm.app.simple_ui import UIConfig, create_ui_factory

# Custom configuration
config = UIConfig(
    assistant_name="MyBot",
    exit_commands=["/quit", "/bye", "/stop"],
    info_commands=["/help", "/?"],
    yolo=False,  # Auto-approve all tools
)

# Pass to factory
llm_chat.set_ui_factory(create_ui_factory(MyUI, config=config, bot=my_bot))
```

---

## Using create_ui_factory()

The `create_ui_factory()` helper eliminates factory boilerplate:

```python
# BEFORE: Verbose factory with 8 parameters
def create_ui(ctx, llm_task_core, history_manager, ui_commands,
              initial_message, initial_conversation_name,
              initial_yolo, initial_attachments):
    return MyUI(
        ctx=ctx,
        llm_task=llm_task_core,
        history_manager=history_manager,
        initial_message=initial_message,
        conversation_session_name=initial_conversation_name,
        yolo=initial_yolo,
        initial_attachments=initial_attachments,
        exit_commands=ui_commands.get("exit", ["/exit"]),
        # ... 10+ more lines
    )

llm_chat.set_ui_factory(create_ui)
```

```python
# AFTER: ONE line with create_ui_factory
from zrb.llm.app.simple_ui import create_ui_factory, UIConfig

config = UIConfig(assistant_name="MyBot")

llm_chat.set_ui_factory(
    create_ui_factory(MyUI, config=config, bot=my_bot, chat_id=CHAT_ID)
)
```

---

## Level 4: BaseUI (For Full Control)

For advanced use cases that need complete control, inherit from `BaseUI` directly.

### Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                     LLMChatTask                             │
│                                                             │
│  ┌─────────────────┐         ┌─────────────────────┐        │
│  │   BaseUI        │         │  ApprovalChannel    │        │
│  │  (Inherit)      │         │                     │        │
│  │                 │         │ request_approval()  │        │
│  │  ask_user()     │         │ notify()            │        │
│  │  append_output()│         │                     │        │
│  │  run_async()    │         │                     │        │
│  └────────┬────────┘         └──────────┬──────────┘        │
│           │                             │                   │
│           │    set_ui_factory()  set_approval_channel()     │
│           └──────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

### Required Methods

| Method | Description |
|--------|-------------|
| `append_to_output()` | Render output to user |
| `ask_user()` | Block and wait for user input |
| `run_interactive_command()` | Execute shell commands |
| `run_async()` | Run the UI event loop |

### Optional Methods

| Method | Default | Description |
|--------|---------|-------------|
| `invalidate_ui()` | No-op | Refresh/redraw UI |
| `on_exit()` | No-op | Cleanup on exit |
| `stream_to_parent()` | Calls append_to_output | Stream to parent UI |

### Example: WebSocket Backend

```python
import asyncio
import json
from websockets.server import serve
from zrb.llm.app.base_ui import BaseUI

class WebSocketUI(BaseUI):
    def __init__(self, websocket, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ws = websocket
        self._input_queue = asyncio.Queue()

    def append_to_output(self, *values, sep=" ", end="\n", **kwargs):
        msg = sep.join(str(v) for v in values) + end
        asyncio.create_task(self.ws.send(msg))

    async def ask_user(self, prompt: str) -> str:
        if prompt:
            await self.ws.send(f"❓ {prompt}")
        return await self._input_queue.get()

    async def run_interactive_command(self, cmd, shell=False):
        await self.ws.send("[Shell commands not supported]")
        return 1

    async def run_async(self) -> str:
        self._process_messages_task = asyncio.create_task(
            self._process_messages_loop()
        )
        if self._initial_message:
            self._submit_user_message(self._llm_task, self._initial_message)

        async def receive_messages():
            async for msg in self.ws:
                data = json.loads(msg)
                if data.get("type") == "user_input":
                    await self._input_queue.put(data["content"])

        receive_task = asyncio.create_task(receive_messages())
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            receive_task.cancel()
            self._process_messages_task.cancel()
        return self.last_output
```

---

## Migration Guide: BaseUI → SimpleUI

### Before (180 lines)
```python
class MyUI(BaseUI):
    def __init__(self, ctx, llm_task, history_manager,
                 yolo_xcom_key, assistant_name,
                 initial_message, initial_attachments,
                 conversation_session_name, yolo, ...):
        super().__init__(
            ctx=ctx, llm_task=llm_task,
            history_manager=history_manager,
            yolo_xcom_key=yolo_xcom_key,
            assistant_name=assistant_name,
            initial_message=initial_message,
            # ... 20+ more parameters
        )
        self.input_queue = asyncio.Queue()
        self.waiting = False

    def append_to_output(self, *values, sep=" ", end="\n", **kwargs):
        # Implementation ...

    async def ask_user(self, prompt: str) -> str:
        # 20 lines of queue logic ...

    async def run_interactive_command(self, cmd, shell=False):
        # Implementation ...

    async def run_async(self) -> str:
        # 30+ lines of boilerplate ...
```

### After (40 lines)
```python
class MyUI(SimpleUI):
    async def print(self, text: str) -> None:
        print(text, end="", flush=True)

    async def get_input(self, prompt: str) -> str:
        if prompt:
            print(f"❓ {prompt}")
        return await asyncio.to_thread(input, "You> ")

# Register
llm_chat.set_ui_factory(create_ui_factory(MyUI))
```

**Size reduction: 78%!**

---

## MultiplexerUI (Multi-Channel Support)

For backends that need to receive input from multiple channels (CLI + Telegram, etc.), use `MultiplexerUI`. See `examples/chat-telegram-cli/` for a complete implementation.

---

## Approval Channels

For tool confirmations, implement `ApprovalChannel`:

```python
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult

class MyApprovalChannel(ApprovalChannel):
    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        # Show tool info
        print(f"🔔 Tool: {context.tool_name}")
        print(f"Args: {context.tool_args}")

        # Get user decision
        response = input("Approve? [Y/n] ")
        approved = response.strip().lower() in ("", "y", "yes")

        return ApprovalResult(approved=approved, message="Approved by user")

    async def notify(self, message: str, context: ApprovalContext | None = None) -> None:
        print(f"📢 {message}")

# Register
llm_chat.set_approval_channel(MyApprovalChannel())
```

### Built-in Approval Channels

| Channel | Description |
|---------|-------------|
| `TerminalApprovalChannel` | Default terminal confirmation |
| `NullApprovalChannel` | Auto-approve everything (YOLO mode) |

### YOLO Mode

To auto-approve all tools:

```python
from zrb.llm.approval import NullApprovalChannel

llm_chat.set_approval_channel(NullApprovalChannel())
```

---

## Working Examples

| Example | Location | Pattern |
|---------|----------|---------|
| Minimal UI | `examples/chat-minimal-ui/` | SimpleUI |
| Telegram | `examples/chat-telegram/` | EventDrivenUI + BufferedOutputMixin |
| Telegram + CLI | `examples/chat-telegram-cli/` | MultiplexerUI |

---

## Pattern Comparison

| Backend | Pattern | `ask_user()` | Complexity |
|---------|---------|--------------|------------|
| **SimpleUI** ||||
| CLI | Request-Response | Blocking | Low |
| File/Queue | Request-Response | Blocking | Low |
| **EventDrivenUI** ||||
| Telegram | Event-Driven | Queue-based | Medium |
| Discord | Event-Driven | Queue-based | Medium |
| WhatsApp | Event-Driven | Queue-based | Medium |
| **PollingUI** ||||
| HTTP API | Polling | Queues | Low |
| WebSocket | Polling | Queues | Low |

**When to use which:**
- **SimpleUI**: You control input (CLI, file-based)
- **EventDrivenUI**: Messages arrive via callbacks (messaging platforms)
- **PollingUI**: External system polls for messages (HTTP API)
- **BufferedOutputMixin**: Rate-limited backends (Telegram, Discord)

---

## Notes

1. **Stripping ANSI Codes**: Remote UIs often do not support terminal ANSI color codes. Use `zrb.util.cli.style.remove_style(text)` to strip these codes before sending text to your remote interface.

2. **Timeouts**: Always implement timeouts for remote channels in `ask_user` and `request_approval` to prevent the agent from hanging indefinitely.

3. **Async methods**: Note that `print()` and `get_input()` are **async** methods. The base class schedules `print()` calls automatically when called from `append_to_output()`.

4. **UI Factory Pattern**: The `set_ui_factory()` method on `llm_chat` allows you to inject custom UI configurations. The factory receives context from the task system.

5. **Session Management**: For multi-user backends (Discord, WhatsApp, Telegram), you need session storage keyed by channel/user ID. Each session has its own UI instance and input queue.