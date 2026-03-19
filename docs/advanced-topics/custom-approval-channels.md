# Custom Approval Channels

Zrb supports multi-channel human-in-the-loop (HITL) approvals for tool calls. This allows you to route approval requests through different channels like Telegram, Web interfaces, Slack, etc.

## Overview

The approval system follows a priority order:

1. **ToolCallHandler** (policy-based) - Check hard rules first
2. **ApprovalChannel** (remote/external) - Human approval for ambiguous cases
3. **CLI Fallback** (terminal input) - Default stdin/stdout prompts

```
Tool Call Request
        │
        ▼
┌─────────────────────────────────────┐
│ 1. ToolCallHandler (Policy-Based)   │
│    └── Hard rules: allow/deny       │
│    └── If decision made → return    │
│    └── If None (no rule) → continue │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│ 2. ApprovalChannel (External)       │
│    └── Telegram, Web, Slack, etc.   │
│    └── If channel exists → ask       │
│    └── If no channel → continue      │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│ 3. CLI Fallback (Terminal)          │
│    └── stdin/stdout prompt          │
│    └── Default behavior              │
└─────────────────────────────────────┘
```

### Core Components

- **`ApprovalChannel`** - Protocol for handling approval requests
- **`ApprovalContext`** - Dataclass containing tool call metadata
- **`ApprovalResult`** - Result with `approved` flag and message
- **`current_approval_channel`** - ContextVar for propagation to nested agents

---

## Built-in Channels

### NullApprovalChannel

Auto-approves all requests (YOLO mode):

```python
from zrb.llm.approval import NullApprovalChannel

channel = NullApprovalChannel()
# All tool calls are automatically approved
```

### TerminalApprovalChannel

Uses the terminal for approval prompts (default behavior):

```python
from zrb.llm.approval import TerminalApprovalChannel
from zrb.llm.tool_call.ui_protocol import UIProtocol

channel = TerminalApprovalChannel(ui=my_ui_instance)
```

---

## Creating Custom Channels

### Basic Custom Channel

Implement the `ApprovalChannel` protocol:

```python
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult


class MyCustomChannel:
    """Simple custom approval channel."""

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        """Handle approval request."""
        # Your custom logic here
        print(f"Tool: {context.tool_name}")
        print(f"Args: {context.tool_args}")
        
        # Get user decision
        response = input("Approve? (y/n): ").strip().lower()
        
        if response in ('y', 'yes'):
            return ApprovalResult(approved=True)
        return ApprovalResult(approved=False, message="User denied")

    async def notify(self, message: str, context: ApprovalContext | None = None):
        """Send notification."""
        print(f"[NOTIFICATION] {message}")
```

### Pattern: Polling-Based Channel

For channels that need to poll for responses (Telegram, Discord, Slack):

```python
import asyncio
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult


class PollingApprovalChannel(ApprovalChannel):
    """Base class for polling-based approval channels."""

    def __init__(self, timeout: int = 300):
        self.timeout = timeout
        self._pending: dict[str, asyncio.Future[ApprovalResult]] = {}

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        """Request approval and wait for response."""
        # Create a future for this request
        loop = asyncio.get_event_loop()
        future: asyncio.Future[ApprovalResult] = loop.create_future()
        self._pending[context.tool_call_id] = future

        # Send the request
        await self._send_request(context)

        try:
            # Wait for response with timeout
            async with asyncio.timeout(self.timeout):
                return await future
        except asyncio.TimeoutError:
            self._pending.pop(context.tool_call_id, None)
            return ApprovalResult(approved=False, message="Timeout")
        finally:
            self._pending.pop(context.tool_call_id, None)

    async def _send_request(self, context: ApprovalContext):
        """Send approval request to external service. Override in subclass."""
        raise NotImplementedError

    def handle_response(self, tool_call_id: str, approved: bool, message: str = ""):
        """Called when response is received from external service."""
        if tool_call_id in self._pending:
            result = ApprovalResult(approved=approved, message=message)
            self._pending[tool_call_id].set_result(result)

    async def notify(self, message: str, context: ApprovalContext | None = None):
        """Send notification. Override in subclass."""
        pass
```

---

## Multi-Channel Approval System

When you want to support multiple approval sources (e.g., Telegram AND CLI), use one of these patterns:

### Pattern 1: Fallback Chain

Try remote channel first, fall back to CLI if timeout or unavailable:

```python
import asyncio
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult


class FallbackApprovalChannel(ApprovalChannel):
    """
    Try primary channel first, fall back to secondary if:
    - Primary channel times out
    - Primary channel is unavailable
    - Primary channel returns None
    """

    def __init__(
        self, 
        primary: ApprovalChannel, 
        fallback: ApprovalChannel,
        primary_timeout: int = 60
    ):
        self.primary = primary
        self.fallback = fallback
        self.primary_timeout = primary_timeout

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        """Try primary, fall back to secondary on failure/timeout."""
        try:
            async with asyncio.timeout(self.primary_timeout):
                result = await self.primary.request_approval(context)
                if result is not None:
                    return result
        except (asyncio.TimeoutError, ConnectionError, Exception) as e:
            # Log the error and fall back
            print(f"Primary channel failed: {e}, falling back to CLI")
        
        # Use fallback channel
        return await self.fallback.request_approval(context)

    async def notify(self, message: str, context: ApprovalContext | None = None):
        """Notify through both channels."""
        try:
            await self.primary.notify(message, context)
        except Exception:
            pass  # Don't fail on notification
        
        try:
            await self.fallback.notify(message, context)
        except Exception:
            pass
```

**Usage:**

```python
from zrb.llm.approval import TerminalApprovalChannel
from my_telegram import TelegramApprovalChannel

# Create channels
telegram = TelegramApprovalChannel(bot_token="...", chat_id="...")
terminal = TerminalApprovalChannel(ui=my_ui)

# Chain: Telegram first, fall back to terminal
approval_channel = FallbackApprovalChannel(
    primary=telegram,
    fallback=terminal,
    primary_timeout=120  # Wait 2 minutes for Telegram response
)

# Use in LLMTask
task = LLMTask(
    name="my_task",
    system_prompt="...",
    approval_channel=approval_channel,
)
```

### Pattern 2: First-Response Wins

Broadcast to all channels, use whichever responds first:

```python
import asyncio
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult


class BroadcastApprovalChannel(ApprovalChannel):
    """
    Send approval request to multiple channels simultaneously.
    Use whichever channel responds first.
    """

    def __init__(self, channels: list[ApprovalChannel], timeout: int = 300):
        self.channels = channels
        self.timeout = timeout

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        """Broadcast to all channels, return first response."""
        
        async def get_response(channel: ApprovalChannel) -> ApprovalResult:
            try:
                return await channel.request_approval(context)
            except Exception as e:
                return ApprovalResult(approved=False, message=f"Error: {e}")

        # Create tasks for all channels
        tasks = [
            asyncio.create_task(get_response(channel))
            for channel in self.channels
        ]

        try:
            async with asyncio.timeout(self.timeout):
                # Wait for first successful response
                done, pending = await asyncio.wait(
                    tasks,
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Cancel pending tasks
                for task in pending:
                    task.cancel()
                
                # Return first completed result
                if done:
                    return await list(done)[0]
                    
        except asyncio.TimeoutError:
            # Cancel all tasks on timeout
            for task in tasks:
                task.cancel()
        
        return ApprovalResult(approved=False, message="All channels timed out")

    async def notify(self, message: str, context: ApprovalContext | None = None):
        """Notify all channels."""
        await asyncio.gather(
            *[channel.notify(message, context) for channel in self.channels],
            return_exceptions=True  # Don't fail if one channel fails
        )
```

**Usage:**

```python
from zrb.llm.approval import TerminalApprovalChannel
from my_telegram import TelegramApprovalChannel
from my_slack import SlackApprovalChannel

# Create channels
telegram = TelegramApprovalChannel(bot_token="...", chat_id="...")
slack = SlackApprovalChannel(webhook_url="...")
terminal = TerminalApprovalChannel(ui=my_ui)

# Broadcast to all, use first response
approval_channel = BroadcastApprovalChannel(
    channels=[telegram, slack, terminal],
    timeout=300  # 5 minute overall timeout
)
```

### Pattern 3: User Choice Channel

Let user choose which channel to use for each approval:

```python
import asyncio
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult


class UserChoiceApprovalChannel(ApprovalChannel):
    """
    Ask user which channel to use, then route to that channel.
    Useful for interactive sessions where user can switch between
    mobile (Telegram) and desktop (CLI).
    """

    def __init__(
        self, 
        channels: dict[str, ApprovalChannel],
        default: str,
        ui_prompt_callback=None
    ):
        """
        Args:
            channels: Dict mapping channel names to channel instances
                     e.g., {"telegram": TelegramChannel(...), "cli": TerminalChannel(...)}
            default: Default channel name
            ui_prompt_callback: Optional async function to ask user for channel choice
        """
        self.channels = channels
        self.default = default
        self.ui_prompt_callback = ui_prompt_callback

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        """Ask user which channel to use, then route."""
        
        # Ask user which channel to use
        if self.ui_prompt_callback:
            channel_name = await self.ui_prompt_callback()
        else:
            channel_name = self.default

        # Get the chosen channel
        channel = self.channels.get(channel_name, self.channels[self.default])
        
        # Route to the chosen channel
        return await channel.request_approval(context)

    async def notify(self, message: str, context: ApprovalContext | None = None):
        """Notify through default channel."""
        channel = self.channels[self.default]
        await channel.notify(message, context)
```

**Usage:**

```python
from zrb.llm.approval import TerminalApprovalChannel
from my_telegram import TelegramApprovalChannel

async def ask_channel() -> str:
    """Ask user which approval channel to use."""
    print("\nApproval required!")
    print("1. Telegram (reply from phone)")
    print("2. Terminal (reply here)")
    choice = input("Choose channel [1/2]: ").strip()
    return "telegram" if choice == "1" else "cli"

# Create channels
telegram = TelegramApprovalChannel(bot_token="...", chat_id="...")
terminal = TerminalApprovalChannel(ui=my_ui)

# Let user choose
approval_channel = UserChoiceApprovalChannel(
    channels={"telegram": telegram, "cli": terminal},
    default="cli",
    ui_prompt_callback=ask_channel
)
```

### Pattern 4: Priority-Based Selection

Try channels in order until one succeeds:

```python
import asyncio
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult


class PriorityApprovalChannel(ApprovalChannel):
    """
    Try channels in priority order until one succeeds.
    Each channel has a timeout.
    """

    def __init__(
        self,
        channels: list[tuple[ApprovalChannel, int]],  # (channel, timeout_seconds)
    ):
        """
        Args:
            channels: List of (channel, timeout) tuples in priority order
                     e.g., [(telegram, 120), (slack, 60), (terminal, 0)]
                     timeout=0 means no timeout (blocking)
        """
        self.channels = channels

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        """Try each channel in order."""
        errors = []

        for channel, timeout in self.channels:
            try:
                if timeout > 0:
                    async with asyncio.timeout(timeout):
                        result = await channel.request_approval(context)
                else:
                    result = await channel.request_approval(context)
                
                # If we got a result, return it
                if result is not None:
                    return result
                    
            except asyncio.TimeoutError:
                errors.append(f"{channel.__class__.__name__}: timeout")
            except Exception as e:
                errors.append(f"{channel.__class__.__name__}: {e}")

        # All channels failed
        return ApprovalResult(
            approved=False,
            message=f"All channels failed: {'; '.join(errors)}"
        )

    async def notify(self, message: str, context: ApprovalContext | None = None):
        """Notify through first available channel."""
        for channel, _ in self.channels:
            try:
                await channel.notify(message, context)
                return
            except Exception:
                continue
```

**Usage:**

```python
from zrb.llm.approval import TerminalApprovalChannel
from my_telegram import TelegramApprovalChannel
from my_slack import SlackApprovalChannel

# Priority: Telegram (2 min) -> Slack (1 min) -> Terminal (no timeout)
approval_channel = PriorityApprovalChannel(
    channels=[
        (TelegramApprovalChannel(...), 120),
        (SlackApprovalChannel(...), 60),
        (TerminalApprovalChannel(ui=my_ui), 0),
    ]
)
```

---

## Telegram Approval Channel Implementation

Here's a complete, working implementation using `python-telegram-bot`:

```python
import asyncio
import logging
from typing import Optional
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult

logger = logging.getLogger(__name__)


class TelegramApprovalChannel(ApprovalChannel):
    """
    Approval channel using Telegram Bot API.
    
    Features:
    - Inline keyboard for approve/deny buttons
    - Timeout handling
    - Session tracking for multi-user support
    """

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        timeout: int = 300,
        approved_text: str = "✅ Approved",
        denied_text: str = "❌ Denied",
    ):
        """
        Args:
            bot_token: Telegram bot token from @BotFather
            chat_id: Chat ID to send approvals to
            timeout: Seconds to wait for response (default 5 minutes)
            approved_text: Text shown when approved
            denied_text: Text shown when denied
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout = timeout
        self.approved_text = approved_text
        self.denied_text = denied_text
        
        self._bot = None
        self._pending: dict[str, asyncio.Future[ApprovalResult]] = {}
        self._application = None

    async def _ensure_bot(self):
        """Lazy initialization of the bot."""
        if self._bot is not None:
            return

        try:
            from telegram.ext import Application, CallbackQueryHandler
            
            # Create application
            self._application = (
                Application.builder()
                .token(self.bot_token)
                .build()
            )
            
            # Add callback handler for inline button presses
            self._application.add_handler(
                CallbackQueryHandler(self._handle_callback)
            )
            
            # Start the bot (without blocking)
            await self._application.initialize()
            await self._application.start()
            await self._application.updater.start_polling()
            
            self._bot = self._application.bot
            
        except ImportError:
            raise ImportError(
                "python-telegram-bot is required. "
                "Install with: pip install python-telegram-bot"
            )

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        """Send approval request to Telegram and wait for response."""
        await self._ensure_bot()

        # Create future for this request
        loop = asyncio.get_event_loop()
        future: asyncio.Future[ApprovalResult] = loop.create_future()
        self._pending[context.tool_call_id] = future

        try:
            # Send message with inline keyboard
            message = await self._send_approval_request(context)
            
            # Wait for response with timeout
            async with asyncio.timeout(self.timeout):
                result = await future
                return result

        except asyncio.TimeoutError:
            # Edit message to show timeout
            try:
                await self._bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=message.message_id,
                    text=f"⏰ Timeout - No response received\n\n{self._format_message(context)}"
                )
            except Exception:
                pass
            
            return ApprovalResult(approved=False, message="Timeout")

        finally:
            self._pending.pop(context.tool_call_id, None)

    async def notify(self, message: str, context: ApprovalContext | None = None):
        """Send a notification without requiring approval."""
        await self._ensure_bot()
        await self._bot.send_message(chat_id=self.chat_id, text=message)

    async def _send_approval_request(self, context: ApprovalContext):
        """Send approval request with inline buttons."""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        text = self._format_message(context)
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve:{context.tool_call_id}"),
                InlineKeyboardButton("❌ Deny", callback_data=f"deny:{context.tool_call_id}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        return await self._bot.send_message(
            chat_id=self.chat_id,
            text=text,
            reply_markup=reply_markup,
        )

    def _format_message(self, context: ApprovalContext) -> str:
        """Format the approval request message."""
        import json
        
        # Pretty print args
        try:
            args_str = json.dumps(context.tool_args, indent=2)
        except Exception:
            args_str = str(context.tool_args)
        
        lines = [
            "🔔 *Tool Approval Request*",
            "",
            f"*Tool:* `{context.tool_name}`",
            f"*ID:* `{context.tool_call_id}`",
        ]
        
        if context.session_id:
            lines.append(f"*Session:* `{context.session_id}`")
        
        lines.extend([
            "",
            "*Arguments:*",
            f"```",
            args_str,
            f"```",
        ])
        
        return "\n".join(lines)

    async def _handle_callback(self, update, context):
        """Handle inline button press."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if not data:
            return
        
        # Parse callback data
        action, tool_call_id = data.split(":", 1)
        
        if tool_call_id not in self._pending:
            await query.edit_message_text("⚠️ Expired or invalid request")
            return
        
        # Set result
        if action == "approve":
            result = ApprovalResult(approved=True, message=self.approved_text)
            await query.edit_message_text(
                f"{self.approved_text}\n\n*Tool:* `{tool_call_id}`",
                parse_mode="Markdown"
            )
        else:
            result = ApprovalResult(approved=False, message=self.denied_text)
            await query.edit_message_text(
                f"{self.denied_text}\n\n*Tool:* `{tool_call_id}`",
                parse_mode="Markdown"
            )
        
        # Resolve the future
        self._pending[tool_call_id].set_result(result)

    async def shutdown(self):
        """Clean shutdown of the bot."""
        if self._application:
            await self._application.updater.stop()
            await self._application.stop()
            await self._application.shutdown()
```

---

## Configuration

### Environment Variable

Set the approval channel factory via environment variable:

```bash
export ZRB_LLM_APPROVAL_CHANNEL_FACTORY="my_module.create_approval_channel"
```

### Configuration Property

Or set it programmatically:

```python
from zrb.config.config import CFG

CFG.LLM_APPROVAL_CHANNEL_FACTORY = "my_module.create_approval_channel"
```

### Factory Function Examples

#### Simple Factory

```python
# my_module.py

import os
from zrb.llm.approval import ApprovalChannel
from my_telegram import TelegramApprovalChannel

def create_approval_channel() -> ApprovalChannel | None:
    """Factory function to create the approval channel."""
    
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if bot_token and chat_id:
        return TelegramApprovalChannel(
            bot_token=bot_token,
            chat_id=chat_id,
            timeout=120  # 2 minute timeout
        )
    
    # No remote channel configured - return None to use CLI fallback
    return None
```

#### Factory with Fallback Chain

```python
# my_module.py

import os
from zrb.llm.approval import ApprovalChannel, NullApprovalChannel
from my_channels import FallbackApprovalChannel, TelegramApprovalChannel, CLIApprovalChannel


def create_approval_channel() -> ApprovalChannel:
    """Factory with fallback chain."""
    
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    # Create CLI fallback (simple stdin/stdout)
    cli = CLIApprovalChannel()  # You'll need to implement this
    
    if bot_token and chat_id:
        telegram = TelegramApprovalChannel(
            bot_token=bot_token,
            chat_id=chat_id,
            timeout=120
        )
        
        return FallbackApprovalChannel(
            primary=telegram,
            fallback=cli,
            primary_timeout=120
        )
    
    # No Telegram configured - just use CLI
    return cli
```

#### Factory with Environment Selection

```python
# my_module.py

import os
from zrb.llm.approval import ApprovalChannel
from my_channels import (
    TelegramApprovalChannel,
    SlackApprovalChannel,
    BroadcastApprovalChannel,
)


def create_approval_channel() -> ApprovalChannel | None:
    """Factory that creates channels based on environment variables."""
    
    channels = []
    
    # Telegram if configured
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    telegram_chat = os.environ.get("TELEGRAM_CHAT_ID")
    if telegram_token and telegram_chat:
        channels.append(TelegramApprovalChannel(
            bot_token=telegram_token,
            chat_id=telegram_chat,
        ))
    
    # Slack if configured
    slack_webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if slack_webhook:
        channels.append(SlackApprovalChannel(webhook_url=slack_webhook))
    
    if not channels:
        return None  # Use CLI fallback
    
    if len(channels) == 1:
        return channels[0]
    
    # Multiple channels: broadcast to all
    return BroadcastApprovalChannel(channels=channels, timeout=300)
```

---

## Integration with LLMTask

### Direct Parameter

```python
from zrb.llm.task.llm_task import LLMTask
from my_channels import TelegramApprovalChannel

channel = TelegramApprovalChannel(bot_token="...", chat_id="...")

task = LLMTask(
    name="my_task",
    system_prompt="You are a helpful assistant.",
    approval_channel=channel,
)
```

### Via Property

```python
from zrb.llm.task.llm_chat_task import LLMChatTask
from my_channels import FallbackApprovalChannel

# Create task first
task = LLMChatTask(name="chat_task")

# Set approval channel later
task.approval_channel = FallbackApprovalChannel(
    primary=TelegramApprovalChannel(...),
    fallback=CLIApprovalChannel(),
)
```

### With Context Propagation

For nested agents, the approval channel is automatically propagated:

```python
from zrb.llm.approval import current_approval_channel

# Set the channel for current context
token = current_approval_channel.set(my_channel)

try:
    # All nested agent calls will use this channel
    await run_agent(...)
finally:
    # Reset when done
    current_approval_channel.reset(token)
```

---

## Testing Custom Channels

### Unit Testing

```python
import asyncio
import pytest
from zrb.llm.approval import ApprovalContext, ApprovalResult


class MockApprovalChannel:
    """Mock channel for testing."""
    
    def __init__(self, auto_approve: bool = True):
        self.auto_approve = auto_approve
        self.requests: list[ApprovalContext] = []
        self.notifications: list[str] = []

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        self.requests.append(context)
        return ApprovalResult(approved=self.auto_approve)

    async def notify(self, message: str, context: ApprovalContext | None = None):
        self.notifications.append(message)


@pytest.mark.asyncio
async def test_approval_flow():
    channel = MockApprovalChannel(auto_approve=True)
    
    context = ApprovalContext(
        tool_name="test_tool",
        tool_args={"arg1": "value1"},
        tool_call_id="call-123",
        session_id="session-456",
    )
    
    result = await channel.request_approval(context)
    
    assert result.approved is True
    assert len(channel.requests) == 1
    assert channel.requests[0].tool_name == "test_tool"


@pytest.mark.asyncio
async def test_fallback_channel():
    from my_channels import FallbackApprovalChannel
    
    # Primary fails, fallback succeeds
    failing_channel = MockApprovalChannel(auto_approve=False)
    working_channel = MockApprovalChannel(auto_approve=True)
    
    fallback = FallbackApprovalChannel(
        primary=failing_channel,
        fallback=working_channel,
    )
    
    context = ApprovalContext(
        tool_name="test",
        tool_args={},
        tool_call_id="123",
    )
    
    result = await fallback.request_approval(context)
    
    # Should use fallback result
    assert result.approved is True
```

---

## Approval Context Fields

The `ApprovalContext` dataclass contains:

| Field | Type | Description |
|-------|------|-------------|
| `tool_name` | `str` | Name of the tool being called |
| `tool_args` | `dict[str, Any]` | Arguments passed to the tool |
| `tool_call_id` | `str` | Unique identifier for this tool call |
| `session_id` | `str \| None` | Session/conversation identifier |
| `conversation_id` | `str \| None` | Conversation identifier |
| `user_id` | `str \| None` | User identifier |
| `extra` | `dict[str, Any]` | Additional metadata |

---

## Best Practices

### 1. Implement Timeouts

Always implement timeouts for remote approval channels:

```python
async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
    try:
        async with asyncio.timeout(300):  # 5 minute timeout
            response = await self._wait_for_response()
    except asyncio.TimeoutError:
        return ApprovalResult(approved=False, message="Approval timeout")
```

### 2. Handle Errors Gracefully

Provide fallback behavior when remote channels fail:

```python
async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
    try:
        result = await self._remote_approval(context)
    except ConnectionError:
        logger.warning("Remote approval unavailable")
        return ApprovalResult(approved=False, message="Connection failed")
    
    return result
```

### 3. Use notify() for Status Updates

Send intermediate status updates via `notify()`:

```python
async def execute_tool(channel):
    await channel.notify("Starting operation...", context)
    # ... execute tool ...
    await channel.notify("Operation completed!", context)
```

### 4. Track Pending Requests

Use `tool_call_id` to match responses to requests:

```python
class MyChannel:
    def __init__(self):
        self._pending: dict[str, asyncio.Future] = {}

    async def request_approval(self, context):
        future = asyncio.Future()
        self._pending[context.tool_call_id] = future
        # ... send request ...
        return await future

    def handle_response(self, tool_call_id, approved):
        if tool_call_id in self._pending:
            self._pending[tool_call_id].set_result(
                ApprovalResult(approved=approved)
            )
```

---

## Related Documentation

- **[LLM Integration](llm-integration.md)** - Overview of LLM features in Zrb
- **[Environment Variables](../configuration/env-vars.md)** - Configuration options
- **[Hooks](hooks.md)** - Hook into agent lifecycle events