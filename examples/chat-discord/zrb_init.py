"""
Discord UI for Zrb LLM Chat

This example extends `llm_chat` to work on Discord instead of terminal.
Set environment variables, then run `zrb llm chat`.

Pattern: Event-Driven (ask_user uses queue, messages routed by handler)

Usage:
    export DISCORD_BOT_TOKEN="your-token"
    export DISCORD_CHANNEL_ID="your-channel-id"  # Optional, restricts to channel
    zrb llm chat
"""

import asyncio
import json
import os

from zrb.builtin.llm.chat import llm_chat
from zrb.llm.app.base_ui import BaseUI
from zrb.llm.approval import ApprovalChannel, ApprovalContext, ApprovalResult
from zrb.util.cli.style import remove_style

BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID")

# ─────────────────────────────────────────────────────────────────────────────
# Shared Discord Bot - Singleton
# ─────────────────────────────────────────────────────────────────────────────


class DiscordBot:
    """Shared Discord bot instance with buffered output."""

    _instance = None

    def __init__(self, token: str, flush_interval: float = 0.5):
        self.token = token
        self.flush_interval = flush_interval
        self._bot = None
        self._ready = asyncio.Event()
        self._buffer: list[str] = []
        self._flush_task: asyncio.Task | None = None
        # Approval handling: message_id -> (tool_call_id, future)
        self._approval_messages: dict[int, tuple[str, asyncio.Future]] = {}
        self._pending_approvals: dict[str, asyncio.Future] = {}

    @classmethod
    def get(cls, token: str = None) -> "DiscordBot":
        if cls._instance is None:
            cls._instance = cls(token or BOT_TOKEN)
        return cls._instance

    async def start(self):
        """Start the bot in background."""
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

        # Start flush loop
        self._flush_task = asyncio.create_task(self._flush_loop())
        return self._bot

    async def _flush_loop(self):
        """Periodically flush buffer."""
        while True:
            await asyncio.sleep(self.flush_interval)
            if self._buffer:
                await self._flush_buffer()

    async def _flush_buffer(self):
        """Send all buffered content."""
        if not self._buffer or not self._bot:
            return
        channel = self._bot.get_channel(int(CHANNEL_ID)) if CHANNEL_ID else None
        if not channel:
            return
        content = "\n".join(self._buffer)
        self._buffer = []
        for chunk in self._split(content, 1900):
            await channel.send(chunk)

    async def send(self, text: str):
        """Buffer text for sending."""
        clean = remove_style(text).strip()
        if clean:
            self._buffer.append(clean)
            # Flush when large
            if len(self._buffer) > 50 or sum(len(s) for s in self._buffer) > 1000:
                await self._flush_buffer()

    async def send_now(self, text: str):
        """Send immediately (for prompts)."""
        if not self._bot:
            return
        channel = self._bot.get_channel(int(CHANNEL_ID)) if CHANNEL_ID else None
        if channel:
            clean = remove_style(text).strip()
            if clean:
                await channel.send(clean[:1900])

    async def send_approval_message(
        self, text: str, tool_call_id: str, future: asyncio.Future
    ) -> None:
        """Send approval message with reactions and track it."""
        if not self._bot:
            return
        channel = self._bot.get_channel(int(CHANNEL_ID)) if CHANNEL_ID else None
        if not channel:
            return
        clean = remove_style(text).strip()
        if not clean:
            return
        message = await channel.send(clean[:1900])
        await message.add_reaction("✅")
        await message.add_reaction("❌")
        # Track this message for approval
        self._approval_messages[message.id] = (tool_call_id, future)

    def resolve_approval(self, message_id: int, approved: bool):
        """Resolve a pending approval (called by reaction handler)."""
        if message_id in self._approval_messages:
            tool_call_id, future = self._approval_messages.pop(message_id)
            if not future.done():
                future.set_result(ApprovalResult(approved=approved))
            # Also clean up pending_approvals
            self._pending_approvals.pop(tool_call_id, None)

    async def flush(self):
        """Manually flush buffer."""
        if self._buffer:
            await self._flush_buffer()

    @staticmethod
    def _split(text: str, max_len: int) -> list[str]:
        if len(text) <= max_len:
            return [text]
        return [text[i : i + max_len] for i in range(0, len(text), max_len)]


# ─────────────────────────────────────────────────────────────────────────────
# Discord UI - Buffered output
# ─────────────────────────────────────────────────────────────────────────────


class DiscordUI(BaseUI):
    """Discord UI with buffered output for cleaner messages."""

    def __init__(self, bot: DiscordBot, channel_id: str, **kwargs):
        super().__init__(**kwargs)
        self.bot = bot
        self.channel_id = channel_id
        self.input_queue: asyncio.Queue = asyncio.Queue()
        self.waiting = False
        self._handler_added = False

    # Required: Buffer output
    def append_to_output(self, *values, sep=" ", end="\n", **kwargs):
        content = remove_style(sep.join(str(v) for v in values) + end)
        asyncio.create_task(self.bot.send(content))

    # Required: Ask user (via queue)
    async def ask_user(self, prompt: str) -> str:
        await self.bot.flush()  # Flush before prompt
        await self.bot.send_now(f"❓ {prompt}")
        self.waiting = True
        try:
            return await self.input_queue.get()
        finally:
            self.waiting = False

    # Required: Shell disabled
    async def run_interactive_command(self, cmd, shell=False):
        await self.bot.send_now("⚠️ Shell disabled")
        return 1

    # Required: Run event loop
    async def run_async(self) -> str:
        await self.bot.start()

        if not self._handler_added:

            @self.bot._bot.event
            async def on_message(message):
                if message.author.bot:
                    return
                if CHANNEL_ID and str(message.channel.id) != CHANNEL_ID:
                    return

                key = f"{message.channel.id}_{message.author.id}"
                ui = _sessions.get(key)
                if not ui:
                    return

                if ui.waiting:
                    await ui.input_queue.put(message.content)
                else:
                    ui._submit_user_message(ui._llm_task, message.content)

            @self.bot._bot.event
            async def on_reaction_add(reaction, user):
                """Handle approval reactions."""
                if user.bot:
                    return
                if CHANNEL_ID and str(reaction.message.channel.id) != CHANNEL_ID:
                    return

                message_id = reaction.message.id
                if message_id not in self.bot._approval_messages:
                    return

                approved = reaction.emoji == "✅"
                self.bot.resolve_approval(message_id, approved)

            self._handler_added = True

        key = f"{self.channel_id}_{id(self)}"
        _sessions[key] = self

        self._process_messages_task = asyncio.create_task(self._process_messages_loop())
        if self._initial_message:
            self._submit_user_message(self._llm_task, self._initial_message)

        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            self._process_messages_task.cancel()
            _sessions.pop(key, None)
        return ""


# Sessions for routing messages
_sessions: dict[str, DiscordUI] = {}


# ─────────────────────────────────────────────────────────────────────────────
# Discord Approval Channel - Uses reactions
# ─────────────────────────────────────────────────────────────────────────────


class DiscordApprovalChannel(ApprovalChannel):
    """Approval via Discord reactions (✅/❌)."""

    def __init__(self, bot: DiscordBot):
        self.bot = bot

    async def request_approval(self, ctx: ApprovalContext) -> ApprovalResult:
        await self.bot.flush()  # Flush before approval request

        # Format the approval message
        args_str = json.dumps(ctx.tool_args, indent=2, default=str)[:800]
        message = f"🔔 **Tool:** `{ctx.tool_name}`\n```\n{args_str}\n```\nReact with ✅ to approve or ❌ to deny."

        # Create future for this approval
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self.bot._pending_approvals[ctx.tool_call_id] = future

        # Send message with reactions (bot tracks message_id -> tool_call_id mapping)
        await self.bot.send_approval_message(message, ctx.tool_call_id, future)

        # Wait for reaction response (with timeout)
        try:
            async with asyncio.timeout(300):
                return await future
        except asyncio.TimeoutError:
            self.bot._pending_approvals.pop(ctx.tool_call_id, None)
            return ApprovalResult(
                approved=False, message="Timeout waiting for approval"
            )

    async def notify(self, msg: str, ctx=None):
        await self.bot.send_now(f"📢 {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# Integrate with zrb llm chat
# ─────────────────────────────────────────────────────────────────────────────

if BOT_TOKEN and CHANNEL_ID:
    discord_bot = DiscordBot.get(BOT_TOKEN)

    def create_ui(
        ctx,
        llm_task_core,
        history_manager,
        ui_commands,
        initial_message,
        initial_conversation_name,
        initial_yolo,
        initial_attachments,
    ):
        return DiscordUI(
            bot=discord_bot,
            channel_id=CHANNEL_ID,
            ctx=ctx,
            yolo_xcom_key="yolo",
            assistant_name="ZrbBot",
            llm_task=llm_task_core,
            history_manager=history_manager,
            initial_message=initial_message,
            conversation_session_name=initial_conversation_name,
            yolo=initial_yolo,
            initial_attachments=initial_attachments,
            exit_commands=ui_commands.get("exit", ["/exit"]),
            info_commands=ui_commands.get("info", ["/help"]),
        )

    llm_chat.set_ui_factory(create_ui)
    llm_chat.set_approval_channel(DiscordApprovalChannel(discord_bot))
    print(f"🤖 Discord ready for channel: {CHANNEL_ID}")
    print("   All interactions via Discord only.")
    print("   Tool approvals: React with ✅/❌")
else:
    print("Set DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID")
    print("Get token: https://discord.com/developers/applications")
