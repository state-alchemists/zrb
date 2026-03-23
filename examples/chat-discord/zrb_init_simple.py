"""
Discord UI - Simplified with EventDrivenUI

This example shows how to create a Discord bot UI with minimal boilerplate
using the new EventDrivenUI base class.

══════════════════════════════════════════════════════════════════════════════
COMPARISON:
══════════════════════════════════════════════════════════════════════════════
BEFORE (BaseUI):                    AFTER (EventDrivenUI):
────────────────────────────────    ────────────────────────────────
- 200 lines                        → 90 lines
- Manual queue pattern              → handle_incoming_message() handles routing
- 25+ constructor params            → 2 methods: print(), start_event_loop()
- Factory with 8 params             → create_ui_factory() one-liner

══════════════════════════════════════════════════════════════════════════════

KEY CONCEPT: EventDrivenUI handles the queue pattern automatically.

When ask_user() is called, it blocks on an internal queue.
When messages arrive from Discord, call handle_incoming_message():
- If waiting for input → message goes to queue (unblocks ask_user)
- If not waiting       → message is submitted to LLM

══════════════════════════════════════════════════════════════════════════════

Usage:
    export DISCORD_BOT_TOKEN="your-token"
    export DISCORD_CHANNEL_ID="your-channel-id"  # Optional
    zrb llm chat
"""

import asyncio
import json
import os

from zrb.builtin.llm.chat import llm_chat
from zrb.llm.app.simple_ui import EventDrivenUI, UIConfig, create_ui_factory
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult
from zrb.util.cli.style import remove_style

BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID")


# =============================================================================
# Discord Bot Singleton
# =============================================================================


class DiscordBot:
    """Shared Discord bot instance with buffered output."""

    _instance = None

    def __init__(self, token: str, channel_id: str | None = None):
        self.token = token
        self.channel_id = channel_id
        self._bot = None
        self._ready = asyncio.Event()

    @classmethod
    def get(
        cls, token: str | None = None, channel_id: str | None = None
    ) -> "DiscordBot":
        if cls._instance is None:
            cls._instance = cls(token or BOT_TOKEN, channel_id)
        return cls._instance

    async def start(self):
        """Initialize and start the bot."""
        if self._bot:
            return self._bot

        import discord
        from discord.ext import commands

        intents = discord.Intents.default()
        intents.message_content = True

        self._bot = commands.Bot(command_prefix="!", intents=intents)

        @self._bot.event
        async def on_ready():
            print(f"🤖 Discord ready: {self._bot.user}")
            self._ready.set()

        asyncio.create_task(self._bot.start(self.token))
        await self._ready.wait()
        return self._bot

    async def send(self, channel_id: str | None, text: str):
        """Send text to Discord channel."""
        if not self._bot:
            return
        channel = self._bot.get_channel(int(channel_id or self.channel_id or 0))
        if not channel:
            return

        clean = remove_style(text).strip()
        if clean:
            for chunk in self._split(clean, 1900):
                await channel.send(chunk)

    @staticmethod
    def _split(text: str, max_len: int) -> list[str]:
        if len(text) <= max_len:
            return [text]
        return [text[i : i + max_len] for i in range(0, len(text), max_len)]


# =============================================================================
# Discord UI - Simplified with EventDrivenUI
# =============================================================================


class DiscordUI(EventDrivenUI):
    """Discord UI using EventDrivenUI - only 2 methods to implement!"""

    def __init__(self, bot: DiscordBot, channel_id: str, **kwargs):
        super().__init__(**kwargs)
        self.bot = bot
        self.channel_id = channel_id

    async def print(self, text: str) -> None:
        """Send output to Discord (simpler than before - no buffering needed)."""
        await self.bot.send(self.channel_id, text)

    async def start_event_loop(self) -> None:
        """Register Discord message handler."""
        await self.bot.start()

        @self.bot._bot.event
        async def on_message(message):
            if message.author.bot:
                return
            if self.bot.channel_id and str(message.channel.id) != self.bot.channel_id:
                return

            # This is the key line - EventDrivenUI handles the rest!
            text = message.content
            self.handle_incoming_message(text)


# =============================================================================
# Discord Approval Channel - Uses reactions (✅/❌)
# =============================================================================

_pending_approvals: dict[str, asyncio.Future] = {}
_approval_messages: dict[int, str] = {}


class DiscordApproval(ApprovalChannel):
    """Handle tool approvals via Discord reactions."""

    def __init__(self, bot: DiscordBot):
        self.bot = bot

    async def request_approval(self, ctx: ApprovalContext) -> ApprovalResult:
        channel = (
            self.bot._bot.get_channel(int(self.bot.channel_id))
            if self.bot._bot
            else None
        )
        if not channel:
            return ApprovalResult(approved=False, message="No Discord channel")

        args_str = json.dumps(ctx.tool_args, indent=2, default=str)[:800]
        text = f"🔔 **Tool:** `{ctx.tool_name}`\n```\n{args_str}\n```\nReact with ✅ to approve or ❌ to deny."

        message = await channel.send(text)
        await message.add_reaction("✅")
        await message.add_reaction("❌")

        _approval_messages[message.id] = ctx.tool_call_id
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        _pending_approvals[ctx.tool_call_id] = future

        try:
            async with asyncio.timeout(300):
                return await future
        except asyncio.TimeoutError:
            _pending_approvals.pop(ctx.tool_call_id, None)
            return ApprovalResult(approved=False, message="Timeout")

    async def notify(self, msg: str, ctx=None):
        channel = (
            self.bot._bot.get_channel(int(self.bot.channel_id))
            if self.bot._bot
            else None
        )
        if channel:
            await channel.send(f"📢 {msg}")


# =============================================================================
# Register reaction handler
# =============================================================================


async def setup_discord_approval_handler(bot: DiscordBot):
    """Register the reaction handler for approvals."""

    @bot._bot.event
    async def on_reaction_add(reaction, user):
        if user.bot:
            return
        message_id = reaction.message.id
        if message_id not in _approval_messages:
            return

        approved = reaction.emoji == "✅"
        tool_call_id = _approval_messages.pop(message_id)

        if tool_call_id in _pending_approvals:
            _pending_approvals.pop(tool_call_id).set_result(
                ApprovalResult(approved=approved)
            )


# =============================================================================
# Integration with zrb llm chat
# =============================================================================

if BOT_TOKEN and CHANNEL_ID:
    bot = DiscordBot.get(BOT_TOKEN, CHANNEL_ID)

    # Configure UI with custom commands
    config = UIConfig(
        assistant_name="DiscordBot",
        exit_commands=["/exit", "/quit"],
    )

    # Create factory - MUCH simpler than before!
    llm_chat.set_ui_factory(
        create_ui_factory(DiscordUI, bot=bot, channel_id=CHANNEL_ID)
    )

    # Setup approval channel
    approval = DiscordApproval(bot)

    # Register reaction handler
    asyncio.create_task(setup_discord_approval_handler(bot))

    print(f"🤖 Discord ready for channel: {CHANNEL_ID}")
    print("   Tool approvals: React with ✅/❌")
else:
    print("Set DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID")
    print("Get token: https://discord.com/developers/applications")
