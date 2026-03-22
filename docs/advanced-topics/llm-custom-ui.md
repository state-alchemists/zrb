# LLM Custom UI and Approval Channels

Zrb's LLM tasks support custom UI and approval channels for non-terminal interfaces like Telegram, Slack, or web applications.

## Extension Hierarchy

Zrb provides multiple levels of UI abstraction, from simplest to most powerful:

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ Level 0: UIProtocol (minimal, 4 methods)                                │
│         - For tool confirmations only                                   │
│         - See: zrb.llm.tool_call.ui_protocol                            │
├─────────────────────────────────────────────────────────────────────────┤
│ Level 1: BaseUI (base class for custom implementations)                │
│         - Implement 4 required methods + run_async()                   │
│         - For custom backends (Telegram, Discord, WebSocket)          │
│         - See: zrb.llm.app.base_ui                                      │
├─────────────────────────────────────────────────────────────────────────┤
│ Level 2: UI (terminal implementation with prompt_toolkit)               │
│         - Full TUI with syntax highlighting, completion, etc.           │
│         - See: zrb.llm.app.ui                                           │
├─────────────────────────────────────────────────────────────────────────┤
│ Level 3: MultiplexerUI (multi-channel support)                          │
│         - Manages multiple child UIs                                    │
│         - See: zrb.llm.multiplexer_ui                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

**Choose the right level:**
- **Level 0 (UIProtocol)**: Only need tool confirmations, not a full chat UI
- **Level 1 (BaseUI)**: Building custom backends (Telegram, Discord, WebSocket, HTTP)
- **Level 2+**: Terminal UI (already implemented by Zrb)

---

## Architecture

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

---

## Quick Start: Creating a Custom UI

To create a custom UI backend, inherit from `BaseUI` and implement 4 required methods:

```python
import asyncio
from zrb.llm.app.base_ui import BaseUI

class MyUI(BaseUI):
    """Custom UI implementation."""
    
    def append_to_output(self, *values, sep=" ", end="\n", **kwargs):
        """Render output to your interface."""
        content = sep.join(str(v) for v in values) + end
        print(content, end="", flush=True)  # or: websocket.send(content)
    
    async def ask_user(self, prompt: str) -> str:
        """Block and wait for user input."""
        if prompt:
            print(prompt, end="", flush=True)
        return await asyncio.to_thread(input, "> ")  # or: await websocket.recv()
    
    async def run_interactive_command(self, cmd, shell=False):
        """Execute shell commands (optional)."""
        proc = await asyncio.create_subprocess_shell(cmd, shell=shell)
        return await proc.wait()
    
    async def run_async(self) -> str:
        """Run the UI event loop."""
        self._process_messages_task = asyncio.create_task(
            self._process_messages_loop()
        )
        if self._initial_message:
            self._submit_user_message(self._llm_task, self._initial_message)
        self._running = True
        try:
            while self._running:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        finally:
            self._process_messages_task.cancel()
        return self.last_output
```

### Using the UI Factory

Connect your UI to the built-in `llm_chat` task:

```python
from zrb.builtin.llm.chat import llm_chat

def create_ui(ctx, llm_task_core, history_manager, ui_commands,
              initial_message, initial_conversation_name,
              initial_yolo, initial_attachments):
    return MyUI(
        ctx=ctx,
        yolo_xcom_key=f"_yolo_{id(ctx)}",
        assistant_name="Assistant",
        llm_task=llm_task_core,
        history_manager=history_manager,
        initial_message=initial_message,
        conversation_session_name=initial_conversation_name,
        yolo=initial_yolo,
        initial_attachments=initial_attachments,
        exit_commands=ui_commands.get("exit", ["/exit"]),
        info_commands=ui_commands.get("info", ["/help"]),
    )

# Hijack the built-in llm_chat task
llm_chat.set_ui_factory(create_ui)
```

---

## BaseUI Required Methods

| Method | Description |
|--------|-------------|
| `append_to_output()` | Render output to user |
| `ask_user()` | Block and wait for user input |
| `run_interactive_command()` | Execute shell commands |
| `run_async()` | Run the UI event loop |

## BaseUI Optional Methods

| Method | Default | Description |
|--------|---------|-------------|
| `invalidate_ui()` | No-op | Refresh/redraw UI |
| `on_exit()` | No-op | Cleanup on exit |
| `stream_to_parent()` | Calls append_to_output | Stream to parent UI |
| `_get_output_field_width()` | None | Width for text wrapping |

---

## Example: WebSocket Backend

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
            await self.ws.send(prompt)
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

async def handle_websocket(websocket):
    ui = WebSocketUI(
        websocket,
        ctx=create_context(),
        yolo_xcom_key="_yolo_ws",
        assistant_name="Assistant",
        llm_task=chat_task,
        history_manager=JsonHistoryManager(data_dir="./history"),
    )
    await ui.run_async()

async def main():
    async with serve(handle_websocket, "localhost", 8765):
        await asyncio.Future()

asyncio.run(main())
```

---

## Example: Request-Response Pattern

For simple backends (file, queue), you can use a straightforward pattern:

```python
import asyncio
from zrb.llm.app.base_ui import BaseUI

class QueueUI(BaseUI):
    def __init__(self, input_queue, output_queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.input_queue = input_queue
        self.output_queue = output_queue

    def append_to_output(self, *values, sep=" ", end="\n", **kwargs):
        content = sep.join(str(v) for v in values) + end
        self.output_queue.put_nowait(content)

    async def ask_user(self, prompt: str) -> str:
        if prompt:
            self.output_queue.put_nowait(prompt)
        return await self.input_queue.get()

    async def run_interactive_command(self, cmd, shell=False):
        self.output_queue.put_nowait("[Commands not supported]")
        return 1

    async def run_async(self) -> str:
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

---

## Event-Driven Pattern (Telegram, Discord)

For event-driven backends like Telegram, the pattern is different:

1. **Cannot block on `ask_user()`** - messages arrive via events
2. **Need message routing** - command vs chat vs `ask_user` response
3. **Need pending questions queue** - track `ask_user` calls

See `examples/telegram-cli/zrb_init.py` for the complete event-driven pattern.

Key differences from request-response:

| Feature | Request-Response | Event-Driven |
|---------|------------------|--------------|
| `ask_user()` | Blocking call | Queue + callback |
| Message handling | Linear | Routed by type |
| Bot lifecycle | None | Polling setup/teardown |
| Pattern | `await input()` | Handler registration |

---

## ApprovalChannel

For tool confirmation UIs (separate from the main chat), implement `ApprovalChannel`:

```python
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult

class ApprovalChannel(Protocol):
    async def request_approval(self, context: ApprovalContext) -> ApprovalResult: ...
    async def notify(self, message: str, context: ApprovalContext | None = None): ...
```

### Built-in Approval Channels

| Channel | Description |
|---------|-------------|
| `TerminalApprovalChannel` | Default terminal confirmation |
| `NullApprovalChannel` | Auto-approve everything (YOLO mode) |

### Setting an Approval Channel

```python
from zrb.builtin.llm.chat import llm_chat
from zrb.llm.approval import NullApprovalChannel

# Auto-approve all tools (YOLO mode)
llm_chat.set_approval_channel(NullApprovalChannel())

# Or use a custom channel
custom_channel = MyApprovalChannel(...)
llm_chat.set_approval_channel(custom_channel)
```

---

## Working Examples

### Request-Response Pattern Examples

These backends can use a simple blocking `ask_user()`:

| Example | Location | Description |
|---------|----------|-------------|
| Minimal UI | `examples/chat-minimal-ui/` | Minimal BaseUI with callbacks |
| WebSocket | `examples/chat-websocket/` | Real-time bidirectional communication |
| HTTP API | `examples/chat-http-api/` | REST API with polling |

### Event-Driven Pattern Examples

These backends need message routing and queues:

| Example | Location | Description |
|---------|----------|-------------|
| Discord | `examples/chat-discord/` | Discord bot with event handling |
| WhatsApp | `examples/chat-whatsapp/` | WhatsApp Business via Twilio |
| Telegram | `examples/telegram-cli/` | MultiplexerUI with multiple channels |

### Pattern Comparison

| Backend | Pattern | `ask_user()` | Message Handling | Complexity |
|---------|---------|--------------|------------------|------------|
| **Request-Response** ||||
| WebSocket | Request-Response | Block on queue | Linear | Low |
| HTTP API | Polling | Block on queue | Linear | Low |
| File/Queue | Request-Response | Block on queue | Linear | Low |
| **Event-Driven** ||||
| Discord | Event-Driven | Queue + routing | Handler registration | Higher |
| WhatsApp | Webhook | Queue + routing | Handler registration | Higher |
| Telegram | Event-Driven | Queue + routing | Handler registration | Higher |

### When to Use Which Pattern

**Request-Response (WebSocket, HTTP, File)**:
- You control the connection
- `ask_user()` can block - the client waits
- Simple linear flow
- Good for: WebSocket servers, HTTP APIs, file-based backends

**Event-Driven (Discord, WhatsApp, Telegram)**:
- Messages arrive via webhook/polling
- `ask_user()` cannot block - must use queues
- Need message routing: is this a command? chat? or response to a question?
- Good for: Messaging platforms, event-based systems

---

## Notes

1. **Stripping ANSI Codes**: Remote UIs often do not support terminal ANSI color codes. Use `zrb.util.cli.style.remove_style(text)` to strip these codes before sending text to your remote interface.

2. **Timeouts**: Always implement timeouts for remote channels in `ask_user` and `request_approval` to prevent the agent from hanging indefinitely if the remote service drops the connection or the user stops responding.

3. **Event-Driven vs Request-Response**:
   - Request-response (WebSocket, HTTP): `ask_user()` can block
   - Event-driven (Telegram, Discord): Need message routing and queue

4. **UI Factory Pattern**: The `set_ui_factory()` method on `llm_chat` allows you to inject custom UI configurations. The factory receives context from the task system.

5. **Session Management**: For multi-user backends (Discord, WhatsApp, Telegram), you need session storage keyed by channel/user ID. Each session has its own UI instance and `ask_user` queue.