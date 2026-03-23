# Telegram + CLI Dual UI Example

This example demonstrates how to run `zrb llm chat` with **both Telegram and CLI simultaneously**, using a shared message queue architecture.

## Architecture

The key insight is that **both UIs share a single message queue**:

```
                    ┌──────────────────────────┐
                    │      MultiplexerUI       │
                    │     (extends BaseUI)     │
                    │                          │
                    │  ┌────────────────────┐  │
                    │  │   _message_queue   │  │  ◄── SINGLE SHARED QUEUE
                    │  │ _process_messages_ │  │
                    │  │ loop()             │  │
                    │  └────────────────────┘  │
                    │           ▲              │
                    │           │              │
                    │  _submit_user_message()  │
                    │           │              │
                    └───────────┬──────────────┘
                                │
              ┌─────────────────┴─────────────────┐
              │                                   │
    ┌─────────┴─────────┐           ┌────────────┴───────────┐
    │  TerminalChildUI  │           │   TelegramChildUI      │
    │  (NOT BaseUI)     │           │   (NOT BaseUI)         │
    │                   │           │                        │
    │  stdin ─────────┐ │           │ ┌─ Telegram message    │
    │                 | │           │ │                      │
    │  _multiplexer ──┼─┼───────────┼─► _multiplexer         │
    └───────────────────┘           └────────────────────────┘
                          │
                    On user input:
                    _multiplexer._submit_from_child(msg)
                                 │
                                 ▼
                    MultiplexerUI._submit_user_message()
                                 │
                                 ▼
                    _message_queue.put_nowait(job)
```

### Why This Works

1. **Single Queue**: Only `MultiplexerUI` has a `_message_queue` (inherited from `BaseUI`)
2. **Child UIs are Thin Adapters**: `TerminalChildUI` and `TelegramChildUI` are NOT `BaseUI` instances - they're simple protocols
3. **Unified Routing**: All user input from any child calls `_submit_from_child()` → `_submit_user_message()` → shared queue
4. **Serialized Execution**: The queue ensures only one LLM request runs at a time

## Approval System

Approvals are also multiplexed - requests go to ALL channels, and the **first response wins**:

```
MultiplexerApprovalChannel
    │
    ├── TerminalApprovalChannel (stdin: "y/n?")
    └── TelegramApprovalChannel (inline buttons)
    
User approves from CLI → Telegram button invalidated
User approves from Telegram → CLI prompt cancelled
```

## Features

- **Dual Output**: LLM responses appear in BOTH Telegram and terminal
- **Dual Input**: Users can type from EITHER Telegram or terminal
- **Multiplexed Approvals**: Approval requests sent to both; first response wins
- **Shared State**: One conversation, one history, synced across channels

## Setup

### 1. Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow the prompts
3. Copy the bot token

### 2. Get Your Chat ID

1. Start a chat with your bot on Telegram
2. Send any message to your bot
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Find the `"chat": {"id": ...}` value

### 3. Install Dependencies

```bash
# Install zrb with LLM support
pip install zrb[llm]

# Install python-telegram-bot for Telegram integration
pip install python-telegram-bot>=20.0
```

### 4. Set Environment Variables

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
export OPENAI_API_KEY="your_openai_key"  # or other LLM provider
```

## Usage

Since `zrb_init.py` automatically loads when you run zrb in this directory:

```bash
cd examples/telegram-cli
zrb llm chat "Hello from both channels!"
```

You should see:
```
🤖 Telegram + CLI multiplexed UI for chat ID: <your_chat_id>
   Chat from Telegram AND terminal!
   Both channels receive all responses.
   Approvals sent to both - first response wins!
```

Now:
- **Telegram**: Receives all LLM responses
- **Terminal**: Receives all LLM responses  
- **Either**: Accept user input

### Example Session

**From Terminal:**
```
💬 14:30 >> Hello!
🤖 14:30 >>
  🔢 Streaming response...
  Hello! I'm your assistant. How can I help you today?
```

**From Telegram (simultaneously):**
```
💬 14:30 >> Hello!

🤖 14:30 >>
Hello! I'm your assistant. How can I help you today?
```

You can reply from **either** location!

## How It Works

### Key Classes

| Class | Parent | Purpose |
|-------|--------|---------|
| `MultiplexerUI` | `BaseUI` | Main UI with shared message queue |
| `TerminalChildUI` | `ChildUIProtocol` | stdin/stdout adapter |
| `TelegramChildUI` | `ChildUIProtocol` | Telegram bot adapter |
| `MultiplexerApprovalChannel` | `ApprovalChannel` | Broadcast approvals |
| `TelegramApprovalChannel` | `ApprovalChannel` | Telegram inline buttons |
| `TerminalApprovalChannel` | `ApprovalChannel` | Terminal y/n prompts |

### Key Methods

```python
# In MultiplexerUI (extends BaseUI)
def _submit_from_child(self, child_ui, message):
    """Called by child UIs when user sends input.
    Routes through the shared queue via _submit_user_message()."""
    
def append_to_output(self, *values):
    """Buffers output for broadcast to ALL children."""
    
def ask_user(self, prompt):
    """Broadcasts prompt to all, waits on primary UI."""
```

```python
# In TerminalChildUI / TelegramChildUI
def send_output(self, message):
    """Display to this channel (print / Telegram send)."""
    
def ask_user(self, prompt):
    """Wait for input from this channel (input / Telegram receive)."""
```

## Extending to More Channels

To add more channels (Slack, Discord, Web, etc.):

1. Implement `ChildUIProtocol`:
   ```python
   class SlackChildUI(ChildUIProtocol):
       def send_output(self, message): ...
       async def ask_user(self, prompt): ...
   ```

2. Add to multiplexer:
   ```python
   child_uis = [terminal_ui, telegram_ui, slack_ui]
   ```

3. Implement an `ApprovalChannel` for approvals.

## Notes

1. **Primary Channel**: Only one channel handles `ask_user()` prompts (configurable). Others just see the prompt.

2. **Security**: Command execution (`/exec`) is disabled in multiplexer mode.

3. **Webhook Conflicts**: If using webhooks, `getUpdates` returns empty. Delete webhooks first:
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/deleteWebhook"
   ```

4. **Thread Safety**: The `asyncio.Queue` is thread-safe and serializes LLM requests automatically.