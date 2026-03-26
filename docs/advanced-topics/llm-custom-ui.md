# LLM Custom UI and Approval Channels

Zrb's LLM tasks support custom UI and approval channels for non-terminal interfaces like Telegram, Slack, Discord, or web applications.

## Mental Model: How the UI Works

### The Core Message Loop

Every UI implementation shares the same underlying architecture:

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                           BaseUI (Core Logic)                           │
│                                                                         │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────┐  │
│  │ User Message    │    │ Message Queue   │    │ LLM Response        │  │
│  │                 │───>│                 │───>│                     │  │
│  │ submit_user_    │    │ process_        │    │ stream_ai_response  │  │
│  │ message()       │    │ messages_loop() │    │                     │  │
│  └─────────────────┘    └─────────────────┘    └─────────────────────┘  │
│         │                                              │                │
│         │                                              ▼                │
│         │                                    ┌──────────────────────┐   │
│         │                                    │ append_to_output()   │   │
│         │                                    │ (display to user)    │   │
│         │                                    └──────────────────────┘   │
│         │                                                               │
│         │         ┌──────────────────────────────────────────┐          │
│         └──────>  │ ask_user() (when approval/prompt needed) │          │
│                   └──────────────────────────────────────────┘          │
│                                                                         │
│  ═════════════════════════════════════════════════════════════════════  │
│  What subclasses implement (the "I/O boundary"):                        │
│                                                                         │
│  BaseUI:        append_to_output(), ask_user(), run_interactive_cmd()   │
│  SimpleUI:      print(), get_input()  (simpler interface)               │
│  EventDrivenUI: print(), start_event_loop() + handle_incoming_message() │
│  PollingUI:     print() + (uses built-in input/output queues)           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Method Mapping: BaseUI → SimpleUI

`SimpleUI` provides default implementations that map to simpler methods:

| BaseUI Method | SimpleUI Method | What SimpleUI Does |
|---------------|-----------------|---------------------|
| `append_to_output(*values, sep, end)` | `print(text: str)` | Joins values with sep/end, calls async `print()` |
| `ask_user(prompt: str)` | `get_input(prompt: str)` | Direct pass-through |
| `run_interactive_command(cmd, shell)` | *(default)* | Shows "not supported" message |
| `run_async()` | *(default)* | Starts `_process_messages_loop()`, handles lifecycle |

### What Each Level Abstracts Away

| Level | What You Implement | What You Get For Free |
|-------|-------------------|----------------------|
| **BaseUI** | `__init__`, `append_to_output()`, `ask_user()`, `run_interactive_command()`, `run_async()` | Message loop, command handling, LLM interaction |
| **SimpleUI** | 2 methods (`print`, `get_input`) | All of BaseUI + simplified `__init__` (UIConfig), default `run_async()` |
| **EventDrivenUI** | 2 methods (`print`, `start_event_loop`) | All of SimpleUI + input queue + message routing |
| **PollingUI** | 0-1 methods (optional `print`) | All of SimpleUI + input/output queues for external polling |

**Key insight:** Each level builds on the previous, reducing what you must implement. `BaseUI` requires understanding the full architecture. `SimpleUI` lets you focus on just input/output.

---

## Quick Start

The simplest way to create a custom UI:

```python
from zrb.builtin.llm.chat import llm_chat
from zrb.llm.app.ui import SimpleUI, create_ui_factory

class MyUI(SimpleUI):
    async def print(self, text: str) -> None:
        """Display output to user. Called when AI responds or system messages."""
        print(text, end="", flush=True)

    async def get_input(self, prompt: str) -> str:
        """Wait for user input. Called for chat input and tool approvals."""
        return await asyncio.to_thread(input, prompt or "You> ")

# One-line registration
llm_chat.set_ui_factory(create_ui_factory(MyUI))
```

**That's it!** Just 2 methods:
- `print()` - Output path (AI responses, system messages)
- `get_input()` - Input path (user chat, approvals, prompts)

---

## UI Extension Levels

Choose your starting point based on your backend type:

| Level | Base Class | Required Methods | Best For |
|-------|-------------|------------------|----------|
| **1** | `SimpleUI` | `print()`, `get_input()` | CLI, file-based, synchronous I/O |
| **2** | `EventDrivenUI` | `print()`, `start_event_loop()` | Telegram, Discord, WhatsApp (callbacks) |
| **3** | `PollingUI` | `print()` (optional) | HTTP API, WebSocket (external polling) |
| **4** | `BaseUI` | `__init__`, `append_to_output()`, `ask_user()`, `run_interactive_command()`, `run_async()` | Full control, custom architecture |

**Recommendation:** Start with `SimpleUI`. Upgrade to `EventDrivenUI` or `PollingUI` if your backend requires it. Use `BaseUI` only for advanced custom architectures.

---

## Level 1: SimpleUI (Request-Response Pattern)

`SimpleUI` is for backends where you **control the event loop** and can **block on input**. You implement just 2 methods:

### Method: `print(text: str)` (async)
- Called when the AI responds, system messages, or errors
- Receives pre-formatted text (already includes emojis, formatting)
- **Must be async** (scheduling handled by base class)

### Method: `get_input(prompt: str)` (async)
- Called when waiting for user input (chat messages, approvals)
- Should block until input is received
- Receive `prompt` (may be empty for approvals)

### Example: Basic CLI

```python
import asyncio
from zrb.builtin.llm.chat import llm_chat
from zrb.llm.app.ui import SimpleUI, create_ui_factory

class CLI(SimpleUI):
    """Minimal CLI implementation."""

    async def print(self, text: str) -> None:
        print(text, end="", flush=True)

    async def get_input(self, prompt: str) -> str:
        return await asyncio.to_thread(input, prompt or "You> ")

llm_chat.set_ui_factory(create_ui_factory(CLI))
```

### Example: File Logger

```python
import asyncio
from pathlib import Path
from zrb.builtin.llm.chat import llm_chat
from zrb.llm.app.ui import SimpleUI, create_ui_factory

class LoggingUI(SimpleUI):
    """Logs all output to file, CLI for input."""

    def __init__(self, log_file: str = "chat.log", **kwargs):
        super().__init__(**kwargs)
        self.log_path = Path(log_file)

    async def print(self, text: str) -> None:
        # Display to terminal
        print(text, end="", flush=True)
        # Append to log file
        self.log_path.write_text(self.log_path.read_text() + text)

    async def get_input(self, prompt: str) -> str:
        return await asyncio.to_thread(input, prompt or "You> ")

llm_chat.set_ui_factory(
    lambda ctx, task, hm, **kw: LoggingUI(
        ctx=ctx, llm_task=task, history_manager=hm, log_file="session.log"
    )
)
```

### Example: Structured Logging UI

```python
import asyncio
import json
from datetime import datetime
from zrb.builtin.llm.chat import llm_chat
from zrb.llm.app.ui import SimpleUI, create_ui_factory

class StructuredLogUI(SimpleUI):
    """Outputs structured JSON for each message."""

    def __init__(self, output_file: str = "messages.jsonl", **kwargs):
        super().__init__(**kwargs)
        self.output_file = output_file

    async def print(self, text: str) -> None:
        record = {
            "timestamp": datetime.now().isoformat(),
            "type": "output",
            "content": text.strip()
        }
        with open(self.output_file, "a") as f:
            f.write(json.dumps(record) + "\n")

    async def get_input(self, prompt: str) -> str:
        return await asyncio.to_thread(input, prompt or "You> ")

llm_chat.set_ui_factory(create_ui_factory(StructuredLogUI))
```

---

## Level 2: EventDrivenUI (Callback Pattern)

For backends where **messages arrive via callbacks/handlers** (Telegram, Discord, WhatsApp), use `EventDrivenUI`.

### The Input Queue Pattern

```text
┌─────────────────────────────────────────────────────────────────┐
│                     EventDrivenUI                               │
│                                                                 │
│  External Handler          Internal Queue          Your Code    │
│                                                                 │
│  on_message(text)  ───>   handle_incoming_   ───>  get_input()  │
│  (callback)               message(text)            (blocks)     │
│                                                                 │
│                           ┌─────────────────┐                   │
│                           │  input_queue    │                   │
│                           │  (asyncio.Queue)│                   │
│                           └─────────────────┘                   │
│                                                                 │
│  If NOT waiting for input:                                      │
│      handle_incoming_message() → submit as new LLM message      │
│  If waiting for input (ask_user blocked):                       │
│      handle_incoming_message() → put to input_queue             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Methods to Implement

| Method | Description |
|--------|-------------|
| `print(text: str)` | Send output to your backend (async) |
| `start_event_loop()` | Register handlers and start listening (async) |

### Key Method: `handle_incoming_message(text)`

Call this when your backend receives a message:

```python
# In your handler:
async def on_telegram_message(update, context):
    text = update.message.text
    self.handle_incoming_message(text)  # Routes automatically!
```

**What it does:**
1. If `get_input()` is blocked waiting → puts text in queue, unblocks it
2. Otherwise → submits text as new message to LLM

### Example: Telegram Bot

```python
import asyncio
from telegram.ext import Application, MessageHandler, filters
from zrb.builtin.llm.chat import llm_chat
from zrb.llm.app.simple_ui import EventDrivenUI, create_ui_factory

class TelegramUI(EventDrivenUI):
    """Telegram bot using EventDrivenUI."""

    def __init__(self, bot_token: str, chat_id: int, **kwargs):
        # Store backend-specific params before super().__init__
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._app = None
        super().__init__(**kwargs)

    async def print(self, text: str) -> None:
        """Send AI response to Telegram."""
        if self._app:
            # Telegram has 4096 char limit per message
            for chunk in self._split_message(text, 4000):
                await self._app.bot.send_message(self.chat_id, chunk)

    async def start_event_loop(self) -> None:
        """Start Telegram bot and register handlers."""
        self._app = Application.builder().token(self.bot_token).build()

        async def handle(update, context):
            text = update.message.text
            # This routes automatically:
            # - If waiting for input → unblocks get_input()
            # - Otherwise → sends to LLM
            self.handle_incoming_message(text)

        self._app.add_handler(MessageHandler(filters.TEXT, handle))
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()

        # Keep running until cancelled
        while True:
            await asyncio.sleep(1)

    def _split_message(self, text: str, max_len: int) -> list[str]:
        """Split long messages while preserving word boundaries."""
        if len(text) <= max_len:
            return [text]
        # Simple split - you may want smarter logic for code blocks
        chunks = []
        while text:
            chunk = text[:max_len]
            last_newline = chunk.rfind('\n')
            if last_newline > max_len // 2:
                chunk = text[:last_newline + 1]
            chunks.append(chunk)
            text = text[len(chunk):]
        return chunks

# Register - ONE line!
llm_chat.set_ui_factory(
    create_ui_factory(TelegramUI, bot_token=BOT_TOKEN, chat_id=CHAT_ID)
)
```

### Example: Discord Bot

```python
import asyncio
import discord
from zrb.builtin.llm.chat import llm_chat
from zrb.llm.app.simple_ui import EventDrivenUI, create_ui_factory

class DiscordUI(EventDrivenUI):
    """Discord bot using EventDrivenUI."""

    def __init__(self, token: str, channel_id: int, **kwargs):
        self.token = token
        self.channel_id = channel_id
        self._client = None
        super().__init__(**kwargs)

    async def print(self, text: str) -> None:
        """Send AI response to Discord."""
        if self._client:
            channel = self._client.get_channel(self.channel_id)
            if channel:
                # Discord has 2000 char limit
                for chunk in [text[i:i+1900] for i in range(0, len(text), 1900)]:
                    # Strip ANSI codes for Discord
                    from zrb.util.cli.style import remove_style
                    await channel.send(remove_style(chunk))

    async def start_event_loop(self) -> None:
        """Start Discord bot and register handlers."""
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

# Register
llm_chat.set_ui_factory(
    create_ui_factory(DiscordUI, token=DISCORD_TOKEN, channel_id=CHANNEL_ID)
)
```

---

## Level 3: PollingUI (Queue-Based Pattern)

For backends where **external systems poll for messages** (HTTP API, WebSocket), use `PollingUI`. It provides built-in queues that external code can use.

### Built-in Queues

```text
┌─────────────────────────────────────────────────────────────────┐
│                        PollingUI                                │
│                                                                 │
│  External Code                    Internal Flow                 │
│                                                                 │
│  ui.output_queue.get()  <───     print() queues output          │
│  (poll for AI responses)                                        │
│                                                                 │
│  ui.input_queue.put(text)  ──>   get_input() receives it        │
│  (provide user responses)                                       │
│                                                                 │
│  ui.run_async()  ──> Starts the LLM message loop                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Minimal Implementation

```python
from zrb.llm.app.simple_ui import PollingUI

class APIUI(PollingUI):
    """HTTP/WebSocket API using PollingUI's queues."""
    # print() already queues to output_queue!
    # get_input() already blocks on input_queue!
    # No additional methods needed!
    pass
```

### Example: HTTP API with aiohttp

```python
import asyncio
import uuid
from aiohttp import web
from zrb.builtin.llm.chat import llm_chat
from zrb.llm.app.simple_ui import PollingUI, create_ui_factory

# Session storage
sessions: dict[str, PollingUI] = {}

class APIUI(PollingUI):
    """HTTP API UI - no additional methods needed."""
    pass

async def handle_create_session(request):
    """Create new chat session."""
    data = await request.json()
    session_id = str(uuid.uuid4())[:8]

    ui = APIUI(
        ctx=request.app["ctx"],  # Your context
        llm_task=llm_chat,
        history_manager=request.app["history_manager"],
        initial_message=data.get("message", ""),  # Optional first message
    )

    sessions[session_id] = ui
    asyncio.create_task(ui.run_async())  # Start message processing

    return web.json_response({"session_id": session_id})

async def handle_poll_responses(request):
    """Poll for AI responses."""
    session_id = request.query.get("session")
    ui = sessions.get(session_id)
    if not ui:
        return web.json_response({"error": "Invalid session"}, status=404)

    messages = []
    while not ui.output_queue.empty():
        messages.append(await ui.output_queue.get())

    return web.json_response({"messages": messages})

async def handle_send_message(request):
    """Send user message."""
    data = await request.json()
    ui = sessions.get(data.get("session"))
    if not ui:
        return web.json_response({"error": "Invalid session"}, status=404)

    # Put message in input queue - get_input() will receive it
    await ui.input_queue.put(data.get("text", ""))
    return web.json_response({"status": "ok"})

# Setup
app = web.Application()
app.add_routes([
    web.post("/session", handle_create_session),
    web.get("/poll", handle_poll_responses),
    web.post("/message", handle_send_message),
])
```

---

## Level 4: BaseUI (Full Control)

Use `BaseUI` when you need complete control over the message loop or have custom architecture requirements.

### What You Must Implement

**5 items total:**

| Item | Purpose | Complexity |
|------|---------|-------------|
| `__init__()` | Initialize with 25+ parameters | Medium (boilerplate) |
| `append_to_output(*values, sep, end, file, flush)` | Display output | Low |
| `ask_user(prompt: str)` | Block for user input | Medium |
| `run_interactive_command(cmd, shell)` | Execute shell commands | Low (or return error) |
| `run_async()` | Start and run event loop | **High** - must manage lifecycle |

### What You Get for Free

- `_process_messages_loop()` - Queue-based message processing
- `_submit_user_message()` - Submit message to LLM
- `_stream_ai_response()` - Handle AI response streaming
- Command handlers (`/help`, `/exit`, `/save`, `/load`, `/model`, `/exec`, `/yolo`)
- History management integration
- Tool confirmation handling

### Example: WebSocket Backend

```python
import asyncio
import json
from websockets.server import serve
from zrb.llm.app.base_ui import BaseUI
from zrb.builtin.llm.chat import llm_chat

class WebSocketUI(BaseUI):
    """WebSocket UI with full control."""

    def __init__(self, websocket, **kwargs):
        super().__init__(**kwargs)
        self.ws = websocket
        self._input_queue: asyncio.Queue[str] = asyncio.Queue()

    def append_to_output(self, *values, sep=" ", end="\n", **kwargs):
        """Send output to WebSocket."""
        text = sep.join(str(v) for v in values) + end
        # Schedule async send
        asyncio.create_task(self.ws.send(text))

    async def ask_user(self, prompt: str) -> str:
        """Wait for user input via WebSocket."""
        if prompt:
            await self.ws.send(f"❓ {prompt}")
        return await self._input_queue.get()

    async def run_interactive_command(self, cmd, shell=False):
        """Shell commands not supported."""
        await self.ws.send("⚠️ Shell commands not supported in WebSocket mode")
        return 1

    async def run_async(self) -> str:
        """Run message loop and WebSocket listener."""
        # Start the message processing loop
        self._process_messages_task = asyncio.create_task(
            self._process_messages_loop()
        )

        # Send initial message if provided
        if self._initial_message:
            self._submit_user_message(self._llm_task, self._initial_message)

        # Listen for WebSocket messages
        async def receive_messages():
            async for msg in self.ws:
                try:
                    data = json.loads(msg)
                    if data.get("type") == "user_input":
                        await self._input_queue.put(data["content"])
                except json.JSONDecodeError:
                    await self.ws.send("❌ Invalid JSON")

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

# Server setup
async def handle_connection(websocket, path):
    ui = WebSocketUI(
        websocket=websocket,
        ctx=...,  # Your context
        llm_task=llm_chat,
        history_manager=...,  # Your history manager
        yolo_xcom_key="yolo",
        assistant_name="AI",
    )
    await ui.run_async()

async def main():
    async with serve(handle_connection, "localhost", 8765):
        await asyncio.Future()  # Run forever
```

---

## BufferedOutputMixin (Rate-Limited Backends)

For backends with **rate limits on message frequency** (Telegram: ~30 messages/sec, Discord: ~5 messages/sec), use `BufferedOutputMixin` to batch output and avoid API throttling.

### Why Buffering?

```text
Without buffering (fragmented):
  LLM streams: "H" → send → "e" → send → "l" → send → "l" → send → "o" → send
  Result: 5 API calls, hits rate limits

With buffering:
  LLM streams: "H" → buffer → "e" → buffer → "l" → buffer → "l" → buffer → "o" → buffer
  After 0.5s: flush → send "Hello"
  Result: 1 API call
```

### Usage Pattern

```python
from zrb.llm.app.simple_ui import EventDrivenUI, BufferedOutputMixin

class TelegramUI(EventDrivenUI, BufferedOutputMixin):
    """Telegram UI with output buffering to avoid rate limits."""

    def __init__(self, bot_token: str, chat_id: int, **kwargs):
        # Initialize EventDrivenUI
        EventDrivenUI.__init__(self, **kwargs)
        # Initialize buffering (0.3s interval, 3000 char max)
        BufferedOutputMixin.__init__(self, flush_interval=0.3, max_buffer_size=3000)

        self.bot_token = bot_token
        self.chat_id = chat_id
        self._app = None

    async def print(self, text: str) -> None:
        """Buffer output instead of sending immediately."""
        self.buffer_output(text)

    async def _send_buffered(self, text: str) -> None:
        """Called automatically when buffer flushes."""
        if self._app:
            await self._app.bot.send_message(self.chat_id, text)

    async def start_event_loop(self) -> None:
        # Start bot
        self._app = Application.builder().token(self.bot_token).build()

        async def handle(update, context):
            self.handle_incoming_message(update.message.text)

        self._app.add_handler(MessageHandler(filters.TEXT, handle))
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()

        # Start periodic flush
        await self.start_flush_loop()

        # Keep running
        while True:
            await asyncio.sleep(1)

    async def on_exit(self):
        """Clean shutdown - flush remaining buffer."""
        await self.stop_flush_loop()
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `flush_interval` | 0.5 | Seconds between flushes |
| `max_buffer_size` | 2000 | Characters before forced flush |

---

## UIConfig: Cleaner Configuration

### The Problem: BaseUI Has 25+ `__init__` Parameters

```python
# BaseUI __init__ signature (simplified)
def __init__(
    self, ctx, llm_task, history_manager,
    yolo_xcom_key, assistant_name, initial_message, initial_attachments,
    conversation_session_name, yolo, triggers, response_handlers,
    tool_policies, argument_formatters, markdown_theme,
    summarize_commands, attach_commands, exit_commands, info_commands,
    save_commands, load_commands, redirect_output_commands,
    yolo_toggle_commands, set_model_commands, exec_commands,
    custom_commands, model,
):
    ...
```

### The Solution: UIConfig Dataclass

```python
from zrb.llm.app.simple_ui import UIConfig, create_ui_factory

# Bundle all configuration in one object
config = UIConfig(
    # Identity
    assistant_name="MyBot",
    
    # Commands (customize or disable)
    exit_commands=["/quit", "/bye", "/stop"],
    info_commands=["/help", "/?"],
    yolo=True,  # Auto-approve all tools
    
    # Disable specific commands
    exec_commands=[],  # No shell access
)

# Pass to factory
llm_chat.set_ui_factory(create_ui_factory(MyUI, config=config))
```

### UIConfig Fields

| Field | Default | Description |
|-------|---------|-------------|
| `assistant_name` | `"Assistant"` | Name shown in prompts |
| `exit_commands` | `["/exit", "/quit"]` | Commands to exit |
| `info_commands` | `["/help", "/?"]` | Show help |
| `save_commands` | `["/save"]` | Save conversation |
| `load_commands` | `["/load"]` | Load conversation |
| `attach_commands` | `["/attach"]` | Attach files |
| `yolo_toggle_commands` | `["/yolo"]` | Toggle auto-approve |
| `set_model_commands` | `["/model"]` | Switch model |
| `exec_commands` | `["/exec"]` | Run shell commands |
| `yolo` | `False` | Auto-approve all tools |
| `conversation_session_name` | `""` | Session name (empty = random) |

---

## create_ui_factory(): One-Line Registration

### The Problem: Factory Boilerplate

Without `create_ui_factory()`, you need to handle 8 parameters:

```python
def create_my_ui(
    ctx,                          # Task context
    llm_task_core,                # LLM task instance
    history_manager,              # History manager
    ui_commands,                  # Dict of command lists
    initial_message,              # First message
    initial_conversation_name,     # Session name
    initial_yolo,                 # Auto-approve mode
    initial_attachments,          # Files to attach
):
    return MyUI(
        ctx=ctx,
        llm_task=llm_task_core,
        history_manager=history_manager,
        initial_message=initial_message,
        conversation_session_name=initial_conversation_name,
        yolo=initial_yolo,
        initial_attachments=initial_attachments,
        # Plus extract commands from ui_commands...
        exit_commands=ui_commands.get("exit", ["/exit"]),
        info_commands=ui_commands.get("info", ["/help"]),
        # ... and 8 more command extractions
    )

llm_chat.set_ui_factory(create_my_ui)
```

### The Solution: Automatic Parameter Handling

```python
from zrb.llm.app.simple_ui import create_ui_factory, UIConfig

# One-line registration with automatic parameter mapping
config = UIConfig(assistant_name="MyBot", yolo=True)
llm_chat.set_ui_factory(
    create_ui_factory(MyUI, config=config, bot_token=TOKEN, chat_id=12345)
)
```

`create_ui_factory()` automatically:
1. Maps the 8 standard parameters to UIConfig
2. Merges `ui_commands` from task configuration
3. Passes your extra kwargs (`bot_token`, `chat_id`) to `MyUI.__init__()`

---

## Level 4: BaseUI (For Full Control)

For advanced use cases that need complete control, inherit from `BaseUI` directly.

### Architecture Overview

```text
┌─────────────────────────────────────────────────────────────────┐
│                     LLMChatTask                                 │
│                                                                 │
│  ┌─────────────────────┐     ┌──────────────────────┐           │
│  │      BaseUI         │     │  ApprovalChannel     │           │
│  │  (Inherit from)     │     │  (Inject separately) │           │
│  │                     │     │                      │           │
│  │  _process_messages_ │     │  request_approval()  │           │
│  │  loop()             │     │  notify()            │           │
│  │  _submit_user_      │     │                      │           │
│  │  message()          │     └──────────────────────┘           │
│  │  _stream_ai_        │                                        │
│  │  response()         │                                        │
│  │  _handle_*_cmd()    │                                        │
│  │                     │                                        │
│  │  ─────────────────  │                                        │
│  │  YOU IMPLEMENT:     │                                        │
│  │  append_to_output() │                                        │
│  │  ask_user()         │                                        │
│  │  run_interactive_   │                                        │
│  │  command()          │                                        │
│  │  run_async()        │                                        │
│  └─────────────────────┘                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### When to Use BaseUI vs SimpleUI

| Use BaseUI When | Use SimpleUI When |
|-----------------|-------------------|
| You need custom `run_async()` logic | Standard event loop is fine |
| You need `run_interactive_command()` | Shell commands not needed |
| You want low-level `append_to_output()` | Simple `print()` is enough |
| You're building a custom multiplexer | Single-channel UI |

### BaseUI Required Methods

| Method | Purpose |
|--------|---------|
| `append_to_output(*values, sep, end, file, flush)` | Called for all output (AI, system, errors) |
| `ask_user(prompt: str)` | Blocks until user responds |
| `run_interactive_command(cmd, shell)` | Execute shell commands (can return error) |
| `run_async()` | Start message loop, manage lifecycle |

### BaseUI Optional Methods

| Method | Default | Purpose |
|--------|---------|---------|
| `invalidate_ui()` | No-op | Redraw/refresh UI |
| `on_exit()` | No-op | Cleanup on shutdown |
| `stream_to_parent()` | Calls `append_to_output` | For multiplexed UIs |
| `_get_output_field_width()` | None | Custom text width for formatting |

---

## Migration Guide: BaseUI → SimpleUI

### What You're Really Saving

| Aspect | BaseUI | SimpleUI | Savings |
|--------|---------|----------|---------|
| **Items to implement** | 5: `__init__`, `append_to_output()`, `ask_user()`, `run_interactive_command()`, `run_async()` | 2: `print()`, `get_input()` | 60% fewer items |
| **`__init__` parameters** | 25+ params | Config object + kwargs | Cleaner initialization |
| **`__init__` boilerplate** | 20+ lines | 1 `super().__init__()` call | Less code |
| **Event loop management** | You write `run_async()` | Handled by default | 30+ lines saved |
| **Shell command handling** | You implement | Shows warning | Optional feature |

### Method Translation

| BaseUI | SimpleUI | Notes |
|--------|----------|-------|
| `append_to_output(*values, sep, end)` | `print(text: str)` | Simpler signature, async |
| `ask_user(prompt)` | `get_input(prompt)` | Same semantics, simpler name |
| `run_interactive_command(cmd)` | *(not supported)* | Returns error by default |
| `run_async()` | *(handled for you)* | Uses `_process_messages_loop()` |

### Example Migration

**Before (BaseUI - ~25 lines of user code):**

```python
class MyUI(BaseUI):
    def __init__(self, ctx, llm_task, history_manager, **kwargs):
        super().__init__(
            ctx=ctx,
            llm_task=llm_task,
            history_manager=history_manager,
            yolo_xcom_key="yolo",
            assistant_name="Bot",
            initial_message="",
            initial_attachments=[],
            conversation_session_name="",
            yolo=False,
            # ... 15 more params
        )

    def append_to_output(self, *values, sep=" ", end="\n", **kwargs):
        text = sep.join(str(v) for v in values) + end
        print(text, end="", flush=True)

    async def ask_user(self, prompt: str) -> str:
        return await asyncio.to_thread(input, prompt or "You> ")

    async def run_interactive_command(self, cmd, shell=False):
        await self.append_to_output("Shell commands not supported\n")
        return 1

    async def run_async(self):
        self._process_messages_task = asyncio.create_task(
            self._process_messages_loop()
        )
        if self._initial_message:
            self._submit_user_message(self._llm_task, self._initial_message)
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            self._process_messages_task.cancel()
        return self.last_output
```

**After (SimpleUI - ~8 lines of user code):**

```python
class MyUI(SimpleUI):
    async def print(self, text: str) -> None:
        print(text, end="", flush=True)

    async def get_input(self, prompt: str) -> str:
        return await asyncio.to_thread(input, prompt or "You> ")

# Registration
llm_chat.set_ui_factory(create_ui_factory(MyUI))
```

**Actual reduction: ~17 fewer lines of boilerplate.**

---

## MultiplexerUI (Multi-Channel Support)

For systems that need **multiple input channels** (CLI + Telegram, Web + CLI), use `MultiplexerUI`. It combines multiple UIs and routes approvals/appropriately.

See `examples/chat-telegram-cli/` for a complete implementation with:
- Combined CLI and Telegram input
- First-response-wins for approvals
- Broadcast output to all channels

---

## Approval Channels

For tool confirmations, implement `ApprovalChannel`:

```python
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult

class TelegramApprovalChannel(ApprovalChannel):
    """Send approval requests to Telegram."""

    def __init__(self, bot, chat_id: int):
        self.bot = bot
        self.chat_id = chat_id

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        """Ask user to approve tool execution."""
        from zrb.util.cli.style import remove_style

        # Show tool info
        msg = (
            f"🔧 Tool Request\n"
            f"Name: {context.tool_name}\n"
            f"Args: {context.tool_args}\n"
            f"\nApprove? (y/n)"
        )
        await self.bot.send_message(self.chat_id, remove_style(msg))

        # Wait for response (you need to implement this)
        response = await self._wait_for_response()
        approved = response.lower() in ("y", "yes", "")

        return ApprovalResult(
            approved=approved,
            message="Approved" if approved else "Denied"
        )

    async def notify(self, message: str, context: ApprovalContext | None = None) -> None:
        """Send notification to user."""
        from zrb.util.cli.style import remove_style
        await self.bot.send_message(self.chat_id, remove_style(message))

# Register
llm_chat.set_approval_channel(TelegramApprovalChannel(bot, CHAT_ID))
```

### ApprovalChannel Interface

| Method | Purpose |
|--------|---------|
| `request_approval(context)` | Ask user to approve/deny tool execution |
| `notify(message, context)` | Send informational message |

### ApprovalContext Fields

| Field | Description |
|-------|-------------|
| `tool_name` | Name of the tool to execute |
| `tool_args` | Arguments passed to the tool |
| `session_name` | Conversation session name |
| `ui` | Reference to UI for output (if needed) |

### Built-in Approval Channels

| Channel | Description |
|---------|-------------|
| `TerminalApprovalChannel` | Default terminal confirmation (uses UI) |
| `NullApprovalChannel` | Auto-approve everything (YOLO mode) |

### YOLO Mode (Auto-Approve All)

```python
from zrb.llm.approval import NullApprovalChannel

# Auto-approve all tool calls
llm_chat.set_approval_channel(NullApprovalChannel())

# Or enable via UIConfig
config = UIConfig(yolo=True)
llm_chat.set_ui_factory(create_ui_factory(MyUI, config=config))
```

---

## Working Examples

| Example | Location | Level | Pattern |
|---------|----------|-------|---------|
| Minimal CLI | `examples/chat-minimal-ui/` | 1 | SimpleUI |
| Telegram Bot | `examples/chat-telegram/` | 2 | EventDrivenUI + BufferedOutputMixin |
| Telegram + CLI | `examples/chat-telegram-cli/` | 2+ | MultiplexerUI (two channels) |
| Discord Bot | `examples/chat-discord/` | 2 | EventDrivenUI |
| WhatsApp Bot | `examples/chat-whatsapp/` | 2 | EventDrivenUI |
| HTTP API | `examples/chat-http-api/` | 3 | PollingUI |
| WebSocket | `examples/chat-websocket/` | 3 | PollingUI |

---

## Pattern Selection Guide

### By Backend Type

| Backend Type | Recommended Level | Why |
|--------------|-------------------|-----|
| CLI / Terminal | `SimpleUI` | You control input flow |
| File logger | `SimpleUI` | Sequential writes |
| Telegram Bot | `EventDrivenUI` + `BufferedOutputMixin` | Callbacks + rate limits |
| Discord Bot | `EventDrivenUI` + `BufferedOutputMixin` | Callbacks + rate limits |
| WhatsApp | `EventDrivenUI` | Webhook callbacks |
| HTTP API | `PollingUI` | External polling |
| WebSocket Server | `PollingUI` | External reads/writes |
| Custom Multiplexer | `BaseUI` | Full control needed |

### By Feature Need

| Need | Use |
|------|-----|
| Standard CLI | `SimpleUI` |
| Event-driven messaging | `EventDrivenUI` |
| External polling | `PollingUI` |
| Rate limit protection | Add `BufferedOutputMixin` |
| Custom event loop | `BaseUI` |
| Multi-channel input | `MultiplexerUI` (see examples) |

---

## Important Notes

### 1. Async Methods

Both `print()` and `get_input()` **must be async**. The base class schedules `print()` calls automatically when `append_to_output()` is called (which may happen from sync context).

```python
# CORRECT - async methods
class MyUI(SimpleUI):
    async def print(self, text: str) -> None:  # ✓ async
        await some_async_send(text)

    async def get_input(self, prompt: str) -> str:  # ✓ async
        return await asyncio.to_thread(input, prompt)

# WRONG - sync methods will cause issues
class BadUI(SimpleUI):
    def print(self, text: str) -> None:  # ✗ Not async
        print(text)
```

### 2. Stripping ANSI Codes

Remote UIs (Telegram, Discord, etc.) don't support terminal ANSI codes. Use `remove_style()`:

```python
from zrb.util.cli.style import remove_style

async def print(self, text: str) -> None:
    clean_text = remove_style(text)  # Strip ANSI codes
    await self.bot.send_message(self.chat_id, clean_text)
```

### 3. Timeouts for Remote Channels

Always implement timeouts to prevent hanging:

```python
async def get_input(self, prompt: str) -> str:
    await self.print(f"❓ {prompt}")
    try:
        # Timeout after 5 minutes
        return await asyncio.wait_for(
            self._input_queue.get(),
            timeout=300
        )
    except asyncio.TimeoutError:
        return "cancel"  # Or raise to abort
```

### 4. Session Management for Multi-User

For multi-user backends, maintain separate UI instances per user/channel:

```python
# Per-user session storage
sessions: dict[int, EventDrivenUI] = {}

async def on_message(update, context):
    user_id = update.message.from_user.id

    # Get or create session
    if user_id not in sessions:
        sessions[user_id] = MyUI(
            ctx=ctx,
            llm_task=llm_chat,
            history_manager=history_manager,
            # ...
        )
        asyncio.create_task(sessions[user_id].run_async())

    # Route message to correct session
    sessions[user_id].handle_incoming_message(update.message.text)
```

### 5. UI Factory Context

The factory receives parameters from `LLMChatTask`:

```python
def factory(
    ctx: AnyContext,              # Task context
    llm_task_core: LLMTask,       # LLM task instance
    history_manager: HistoryManager,  # History manager
    ui_commands: dict,            # Command configuration
    initial_message: str,         # First message (if any)
    initial_conversation_name: str,  # Session name
    initial_yolo: bool,          # Auto-approve mode
    initial_attachments: list,    # Files to attach
) -> BaseUI:
    ...
```

Use `create_ui_factory()` to handle this automatically.

---

## Summary

| Level | Implements | Best For | Complexity |
|-------|------------|----------|------------|
| `SimpleUI` | `print()`, `get_input()` | CLI, file logging | Low |
| `EventDrivenUI` | `print()`, `start_event_loop()` | Telegram, Discord | Medium |
| `PollingUI` | `print()` (optional) | HTTP API, WebSocket | Low |
| `BaseUI` | `__init__`, `append_to_output()`, `ask_user()`, `run_interactive_command()`, `run_async()` | Custom architectures | High |

**Start with `SimpleUI`**. Upgrade only when your backend requires it.