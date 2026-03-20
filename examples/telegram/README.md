# Telegram LLM Bot Example

This example shows how to run `LLMChatTask` on Telegram with both UI and approval channel routed through Telegram.

## Features

- **Telegram UI**: User messages and agent responses flow through Telegram
- **Telegram Approvals**: Tool call confirmations use inline Approve/Deny buttons
- **Non-interactive mode**: Runs as a background bot, not terminal-based

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Telegram Bot                    │
│                                                 │
│  ┌──────────────┐      ┌──────────────────┐   │
│  │ TelegramUI   │      │ TelegramApproval  │   │
│  │              │      │ Channel           │   │
│  │ ask_user()   │      │ request_approval()│   │
│  │ stream_output│      │ notify()          │   │
│  └──────┬───────┘      └────────┬─────────┘   │
│         │                       │              │
│         │   set_ui()   set_approval_channel()  │
│         └───────────────────────┘              │
│                     │                          │
│              LLMChatTask                        │
│            (interactive=False)                  │
└─────────────────────────────────────────────────┘
```

## Setup

### 1. Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow the prompts
3. Copy the bot token

### 2. Get Your Chat ID

1. Start a chat with your bot
2. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. Find `"chat":{"id":<YOUR_CHAT_ID>}` in the response

### 3. Install Dependencies

```bash
pip install zrb[llm] python-telegram-bot
```

### 4. Set Environment Variables

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
export OPENAI_API_KEY="your_openai_key"  # or other LLM provider
```

## Usage

### Run as Bot

```bash
cd examples/telegram
python -m zrb run llm-telegram-chat
```

Or run directly:

```bash
python zrb_init.py
```

### Programmatic Usage

```python
import asyncio
from zrb_init import TelegramLLMBot

async def main():
    bot = TelegramLLMBot(
        bot_token="YOUR_BOT_TOKEN",
        chat_id="YOUR_CHAT_ID",
        system_prompt="You are a helpful assistant.",
        model="openai:gpt-4o",
    )
    
    await bot.start()
    
    # Handle a single message
    response = await bot.handle_message("What's the weather?")
    print(response)
    
    # Or run forever in polling mode
    # await bot.run_forever()
    
    await bot.shutdown()

asyncio.run(main())
```

## Key Components

### TelegramUI

Implements `UIProtocol` for Telegram-based user interaction:

- `ask_user()` - Sends question to Telegram, waits for response
- `append_to_output()` - Buffers output for batch sending
- `stream_to_parent()` - Sends output immediately
- `flush_output()` - Sends all buffered output

### TelegramApprovalChannel

Implements `ApprovalChannel` for Telegram-based tool confirmations:

- `request_approval()` - Sends message with inline Approve/Deny buttons
- `notify()` - Sends status notifications

### TelegramLLMBot

Wraps everything together:

- Creates and configures `LLMChatTask`
- Sets UI and approval channel
- Handles message routing

## Customization

### Different LLM Provider

```python
bot = TelegramLLMBot(
    bot_token="...",
    chat_id="...",
    model="anthropic:claude-3-opus",  # Use Claude
)
```

### Custom Timeout

```python
bot = TelegramLLMBot(
    bot_token="...",
    chat_id="...",
    message_timeout=600,   # 10 min for user response
    approval_timeout=300,  # 5 min for approvals
)
```

### Add Tools

```python
from zrb import LLMChatTask
from pydantic_ai import Tool

def my_tool(query: str) -> str:
    """A custom tool."""
    return f"Result: {query}"

task = LLMChatTask(
    name="bot",
    tools=[Tool(my_tool)],
    interactive=False,
)
task.set_ui(ui)
task.set_approval_channel(approval)
```

## Notes

1. **`interactive=False`** - Required for non-terminal UIs like Telegram
2. **Both components use the same bot** - UI and approval channel share the Telegram connection
3. **Security** - Command execution (`run_interactive_command`) is disabled from Telegram
4. **Long messages** - Automatically truncated to fit Telegram's 4096 character limit