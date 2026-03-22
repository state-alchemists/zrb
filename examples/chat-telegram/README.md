# Telegram LLM Bot Example

This example shows how to make `zrb llm chat` work on Telegram instead of the terminal.
By setting custom UI and approval channels, the existing `llm_chat` task will use Telegram, while keeping all of its built-in tools and capabilities.

## Architecture

When you run `zrb llm chat` normally, it uses the terminal for input/output and tool approvals.
By importing the task and setting `interactive=False`, `set_ui()`, and `set_approval_channel()`, we can "hijack" the interface and route everything to Telegram.

## Setup

### 1. Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow the prompts
3. Copy the bot token

### 2. Get Your Chat ID

1. Start a chat with your bot on Telegram
2. Send any message to your bot
3. (If you previously set a webhook) Delete it first:
   ```bash
   curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/deleteWebhook"
   ```
4. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
5. Find the `"chat"` object in the response, e.g.:
   ```json
   {"ok":true,"result":[{"message":{"chat":{"id":123456789,...}}}]}
   ```
6. Copy the `id` value (this is your `TELEGRAM_CHAT_ID`)

> **Note:** If `getUpdates` returns `{"ok":true,"result":[]}`, either:
> - You haven't sent a message to your bot yet, or
> - A webhook is already set (webhooks and `getUpdates` are mutually exclusive)

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

Since `zrb_init.py` automatically loads when you run zrb in this directory, you simply run the standard `chat` command:

```bash
cd examples/telegram
zrb llm chat "Please analyze my codebase"
```

You should see:
```
🤖 Telegram hijacked llm_chat for chat ID: <your_chat_id>
   The LLM will now interact with you on Telegram!
```

The command will run in your terminal, but all conversational output, questions, and tool approval requests will be sent to your Telegram app. You reply directly in Telegram!

## How it works (in `zrb_init.py`)

```python
# 1. Create Telegram implementations
telegram_ui = TelegramUI(bot_token=BOT_TOKEN, chat_id=CHAT_ID)
telegram_approval = TelegramApprovalChannel(bot_token=BOT_TOKEN, chat_id=CHAT_ID)

# 2. Import the existing, fully-featured llm_chat task
from zrb.builtin.llm.chat import llm_chat

# 3. Hijack it for Telegram!
llm_chat.interactive = False  # Disable the terminal TUI
llm_chat.set_ui(telegram_ui)
llm_chat.set_approval_channel(telegram_approval)
```

## Notes

1. **`interactive=False`** - Required to stop `llm_chat` from launching its fullscreen terminal UI.
2. **Security** - Command execution (`run_interactive_command`) is disabled from Telegram for safety.
3. **Webhook conflict** - If a webhook is set, `getUpdates` returns empty; delete webhook first.