# Telegram + CLI Chat Example

This example supports **three modes** based on environment variables:

1. **CLI only** (default) - Just run `zrb llm chat`
2. **Telegram only** - Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
3. **CLI + Telegram** (dual) - Both channels receive messages

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

### Modes

**CLI only** (no env vars):
```
💬 CLI mode. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID for dual mode.
```

**Dual mode** (with env vars):
```
🤖 Telegram + CLI dual mode for chat ID: 123456789
   Both channels receive all messages.
   Approvals work from both - first response wins!
```

## How It Works

```python
# Add Telegram UI alongside default terminal UI
llm_chat.append_ui_factory(create_ui_factory(TelegramUI, bot=bot, chat_id=CHAT_ID))

# Add Telegram approval alongside terminal approval
llm_chat.append_approval_channel(TelegramApproval(bot, CHAT_ID))
llm_chat.append_approval_channel(TerminalApprovalChannel())
```

The framework automatically creates:
- `MultiUI` to broadcast output to all UIs
- `MultiplexApprovalChannel` to wait for first approval response

## Features

- **Dual Output**: LLM responses appear in BOTH Telegram and terminal
- **Dual Input**: Reply from EITHER Telegram or terminal
- **Multiplexed Approvals**: Approve/deny from either channel
- **Shared History**: One conversation, synced across channels
