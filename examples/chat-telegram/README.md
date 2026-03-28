# Telegram + CLI Chat Example

This example provides **CLI + Telegram dual mode** chat.
Both Telegram and terminal receive all messages and can respond.

## Setup

### 1. Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow the prompts
3. Copy the bot token

### 2. Get Your Chat ID

1. Start a chat with your bot
2. Send any message to your bot
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Find the `"chat": {"id": ...}` value

### 3. Install Dependencies

```bash
pip install zrb[llm]
pip install python-telegram-bot>=20.0
```

### 4. Set Environment Variables

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
```

## Usage

```bash
cd examples/chat-telegram
zrb llm chat "Hello!"
```

**Note:** Both environment variables **must** be set. If not, the example will exit with an error.

Output:
```
🤖 Telegram + CLI dual mode for chat ID: 123456789
   Both channels receive all messages.
   Approvals work from both - first response wins!
```

## How It Works

When you run `zrb llm chat` from this directory:

1. The example checks for `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` environment variables
2. If both are set, it registers a Telegram UI factory alongside the default terminal UI
3. It also registers a Telegram approval channel alongside terminal approval

```python
# Add Telegram UI alongside default terminal UI (dual mode)
llm_chat.append_ui_factory(telegram_ui_factory)

# Add Telegram approval alongside terminal approval
llm_chat.append_approval_channel(telegram_approval)
```

The framework automatically creates:
- **Dual UI**: Messages broadcast to both Telegram and terminal
- **Multiplexed Approvals**: First response from either channel wins
- **Edit routing**: Telegram messages route to approval channel when editing tool arguments

## Features

- **Dual Output**: LLM responses appear in BOTH Telegram and terminal
- **Dual Input**: Reply from EITHER Telegram or terminal
- **Multiplexed Approvals**: Approve/deny from either channel (first response wins)
- **Tool Argument Editing**: Edit tool arguments via Telegram with JSON/YAML support
- **Shared History**: One conversation, synced across channels
- **Message Splitting**: Long messages automatically split for Telegram's 4000-character limit
