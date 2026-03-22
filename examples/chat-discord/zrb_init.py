"""
Discord UI Example for Zrb LLM Chat

This example demonstrates how to create a Discord bot UI for LLM chat
using BaseUI. This is an EVENT-DRIVEN pattern where ask_user() CANNOT block.

Pattern: Event-Driven
    - Bot receives message event -> routes to message handler
    - ask_user() puts question in queue, returns immediately
    - Bot must watch for ask_user responses in message handler

Architecture:
    ┌─────────────────┐                    ┌─────────────────┐
    │  Discord Server │                    │   DiscordUI     │
    │   (Messages)    │                    │   (BaseUI)      │
    └────────┬────────┘                    └────────┬────────┘
             │                                      │
             │  on_message (event)                   │
             │ ──────────────────────────────────────>│
             │                                      │
             │                    _submit_user_message│
             │                                      │
             │  Discord message (output)            │
             │ <─────────────────────────────────────│
             │                                      │
             │  on_reaction (approval)              │
             │ ──────────────────────────────────────>│
             │                                      │

Key Differences from Request-Response:
    - ask_user() CANNOT block (Discord requires async response)
    - Must use queues for ask_user responses
    - Bot must route messages to correct handler
    - Need conversation state per channel/user

Usage:
    # Set environment variables:
    export DISCORD_BOT_TOKEN="your-bot-token"
    export DISCORD_CHANNEL_ID="your-channel-id"  # Optional

    cd examples/chat-discord
    zrb llm chat
"""

import asyncio
import os
from typing import Any

import discord
from discord.ext import commands

from zrb.builtin.llm.chat import llm_chat
from zrb.context.any_context import AnyContext
from zrb.llm.app.base_ui import BaseUI
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.task.llm_task import LLMTask

# =============================================================================
# Configuration
# =============================================================================

DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
DISCORD_CHANNEL_ID = os.environ.get(
    "DISCORD_CHANNEL_ID", None
)  # Optional: restrict to channel

# Discord UI prefix for commands
BOT_PREFIX = os.environ.get("DISCORD_BOT_PREFIX", "!")


# =============================================================================
# Conversation State (Per Channel/User)
# =============================================================================


class ConversationState:
    """State for a single Discord conversation (per channel/user)."""

    def __init__(self, channel_id: int, user_id: int):
        self.channel_id = channel_id
        self.user_id = user_id
        self.ui: "DiscordUI" | None = None
        self.pending_questions: asyncio.Queue = asyncio.Queue()
        self.ask_user_queue: asyncio.Queue = asyncio.Queue()
        self.waiting_for_ask_user: bool = False
        self.current_question_message_id: int | None = None


# Global conversation states
_conversations: dict[str, ConversationState] = {}


def get_conversation_key(channel_id: int, user_id: int) -> str:
    return f"{channel_id}_{user_id}"


# =============================================================================
# Discord UI Implementation
# =============================================================================


class DiscordUI(BaseUI):
    """Discord-based UI for LLM Chat.

    This demonstrates the EVENT-DRIVEN pattern:

    1. Bot receives message -> routes to correct handler
    2. ask_user() puts question in queue, returns immediately
    3. Bot watches for responses in message handler
    4. Must maintain conversation state per channel/user

    Key challenge: ask_user() CANNOT block because:
    - Discord requires async responses
    - Bot must stay responsive to other events
    - Multiple conversations may be active

    Solution: Use queues and message routing.
    """

    def __init__(
        self,
        channel: discord.abc.Messageable,
        author: discord.User,
        ctx: AnyContext,
        llm_task: LLMTask,
        history_manager: AnyHistoryManager,
        **kwargs,
    ):
        super().__init__(
            ctx=ctx,
            yolo_xcom_key=f"_yolo_discord_{channel.id}_{author.id}",
            assistant_name=kwargs.get("assistant_name", "ZrbBot"),
            llm_task=llm_task,
            history_manager=history_manager,
            initial_message=kwargs.get("initial_message", ""),
            initial_attachments=kwargs.get("initial_attachments", []),
            conversation_session_name=kwargs.get("conversation_session_name", ""),
            yolo=kwargs.get("yolo", False),
            exit_commands=kwargs.get("exit_commands", ["/exit", "/quit"]),
            info_commands=kwargs.get("info_commands", ["/help", "/?"]),
        )
        self.channel = channel
        self.author = author
        self._ask_user_queue: asyncio.Queue = asyncio.Queue()
        self._waiting_for_response: bool = False
        self._current_question_id: int | None = None
        self._running = False

    # ==========================================================================
    # REQUIRED METHODS - BaseUI implementation
    # ==========================================================================

    async def send_discord_message(self, content: str, **kwargs):
        """Send message to Discord channel with chunking.

        Discord has a 2000 character limit per message.
        """
        # Split long messages into chunks
        max_length = 1900  # Leave room for formatting
        if len(content) <= max_length:
            await self.channel.send(content[:max_length], **kwargs)
        else:
            # Split by newlines to avoid breaking in the middle of words
            lines = content.split("\n")
            current_chunk = ""
            for line in lines:
                if len(current_chunk) + len(line) + 1 > max_length:
                    if current_chunk:
                        await self.channel.send(current_chunk, **kwargs)
                    current_chunk = line + "\n"
                else:
                    current_chunk += line + "\n"
            if current_chunk.strip():
                await self.channel.send(current_chunk, **kwargs)

    def append_to_output(self, *values, sep=" ", end="\n", file=None, flush=False):
        """Send output to Discord channel.

        NOTE: This is called from sync context, so we schedule the send.
        """
        content = sep.join(str(v) for v in values) + end

        # Schedule the Discord send (Discord requires async)
        asyncio.create_task(self.send_discord_message(content))

        # Track for result extraction
        if (
            content.strip()
            and not content.startswith("\n")
            and not content.startswith("🤖")
        ):
            self._last_result_data = content.rstrip("\n")

    async def ask_user(self, prompt: str) -> str:
        """Wait for user input from Discord.

        EVENT-DRIVEN PATTERN:
        1. Send question to Discord
        2. Put ourselves in waiting state
        3. Return immediately (queue-based wait)
        4. Message handler will put response in queue
        """
        # Send question to Discord
        question_embed = discord.Embed(
            title="❓ Question",
            description=prompt,
            color=discord.Color.blue(),
        )
        message = await self.channel.send(embed=question_embed)

        # Store question message for tracking (user may reply to it)
        self._current_question_id = message.id
        self._waiting_for_response = True

        try:
            # BLOCKING: Wait for message handler to put response
            # This is safe because Discord bot runs in its own task
            response = await self._ask_user_queue.get()
            return response
        finally:
            self._waiting_for_response = False
            self._current_question_id = None

    async def run_interactive_command(self, cmd: str | list[str], shell: bool = False):
        """Execute shell command and send output to Discord."""
        cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)

        # Announce command
        await self.channel.send(f"💻 Running: `{cmd_str}`")

        try:
            process = await asyncio.create_subprocess_shell(
                cmd_str,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if stdout:
                output = stdout.decode()
                await self.send_discord_message(f"```\n{output}\n```")
            if stderr:
                error = stderr.decode()
                await self.send_discord_message(f"❌ Error:\n```\n{error}\n```")

            return process.returncode
        except Exception as e:
            await self.channel.send(f"❌ Failed: {e}")
            return 1

    async def run_async(self) -> str:
        """Run the Discord UI event loop.

        This is simple for Discord:
        - Start message processing
        - Send initial message if provided
        - The Discord bot handles the rest
        """
        self._process_messages_task = asyncio.create_task(self._process_messages_loop())

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
            try:
                await self._process_messages_task
            except asyncio.CancelledError:
                pass

        return self.last_output

    def on_exit(self):
        """Cleanup on exit."""
        self._running = False
        asyncio.create_task(self.channel.send("👋 Conversation ended. Goodbye!"))

    # ==========================================================================
    # Discord-specific methods
    # ==========================================================================

    async def provide_ask_user_response(self, response: str):
        """Called from message handler when user responds to ask_user."""
        await self._ask_user_queue.put(response)

    def is_waiting_for_response(self) -> bool:
        """Check if we're waiting for ask_user response."""
        return self._waiting_for_response


# =============================================================================
# Discord Bot Setup
# =============================================================================

# Bot intents
intents = discord.Intents.default()
intents.message_content = True  # Required to read message content
intents.reactions = True  # For approval reactions

# Create bot
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)


@bot.event
async def on_ready():
    """Called when bot is ready."""
    print(f"Discord bot logged in as {bot.user}")
    print(f"Listening in channels. Prefix: '{BOT_PREFIX}'")
    print(f"Mention the bot to start a conversation: @{bot.user.name}")


@bot.event
async def on_message(message: discord.Message):
    """Handle incoming Discord messages.

    This is the EVENT-DRIVEN entry point.
    Messages must be routed to the correct conversation handler.
    """
    # Ignore bot's own messages
    if message.author == bot.user:
        return

    # Ignore messages from other bots
    if message.author.bot:
        return

    # If restricted to specific channel, ignore others
    if DISCORD_CHANNEL_ID and message.channel.id != int(DISCORD_CHANNEL_ID):
        return

    # Get or create conversation
    conv_key = get_conversation_key(message.channel.id, message.author.id)
    if conv_key not in _conversations:
        # New conversation
        _conversations[conv_key] = ConversationState(
            channel_id=message.channel.id,
            user_id=message.author.id,
        )

    conv = _conversations[conv_key]

    # Check if this is a response to ask_user
    if conv.ui and conv.ui.is_waiting_for_response():
        await conv.ui.provide_ask_user_response(message.content)
        await message.add_reaction("✅")
        return

    # Handle commands
    if message.content.startswith(BOT_PREFIX):
        await bot.process_commands(message)
        return

    # Regular message - submit to LLM (would need proper UI factory setup)
    # In production, you'd create the UI properly with ctx, llm_task, etc.
    # This is a simplified example.
    if conv.ui:
        conv.ui._submit_user_message(conv.ui._llm_task, message.content)
    else:
        await message.channel.send(
            "⚠️ Conversation not initialized. Use !start to begin."
        )


@bot.command(name="start")
async def start_conversation(ctx: commands.Context):
    """Start a new LLM conversation."""
    conv_key = get_conversation_key(ctx.channel.id, ctx.author.id)

    if conv_key in _conversations and _conversations[conv_key].ui:
        await ctx.send("💬 Continuing existing conversation.")
        return

    await ctx.send("🤖 Starting new conversation...")

    # In production, you'd create the UI properly:
    # ui = DiscordUI(ctx.channel, ctx.author, **kwargs)
    # asyncio.create_task(ui.run_async())

    await ctx.send("⚠️ Note: This is an example. In production, connect to llm_chat.")


@bot.command(name="stop")
async def stop_conversation(ctx: commands.Context):
    """Stop the current conversation."""
    conv_key = get_conversation_key(ctx.channel.id, ctx.author.id)

    if conv_key in _conversations:
        conv = _conversations[conv_key]
        if conv.ui:
            conv.ui.on_exit()
        del _conversations[conv_key]
        await ctx.send("👋 Conversation ended.")
    else:
        await ctx.send("⚠️ No active conversation.")


@bot.command(name="help")
async def show_help(ctx: commands.Context):
    """Show available commands."""
    embed = discord.Embed(
        title="🤖 ZrbBot Commands",
        description="A Discord bot powered by LLM.",
        color=discord.Color.blue(),
    )
    embed.add_field(
        name=f"{BOT_PREFIX}start", value="Start a conversation", inline=False
    )
    embed.add_field(
        name=f"{BOT_PREFIX}stop", value="End the conversation", inline=False
    )
    embed.add_field(
        name=f"{BOT_PREFIX}yolo", value="Toggle auto-approve mode", inline=False
    )
    embed.add_field(name="Chat", value="Just send a message to chat!", inline=False)
    await ctx.send(embed=embed)


# =============================================================================
# Running the Bot
# =============================================================================


def run_discord_bot():
    """Run the Discord bot."""
    if not DISCORD_BOT_TOKEN:
        print("Error: DISCORD_BOT_TOKEN environment variable not set.")
        print("Get your bot token from: https://discord.com/developers/applications")
        print("Then run: export DISCORD_BOT_TOKEN='your-token'")
        return

    print(f"Starting Discord bot with prefix: '{BOT_PREFIX}'")
    print(
        f"Channel restriction: {'None' if not DISCORD_CHANNEL_ID else DISCORD_CHANNEL_ID}"
    )

    bot.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    run_discord_bot()


# =============================================================================
# Integration with zrb llm chat
# =============================================================================

"""
To integrate with zrb llm chat:

1. Create a UI factory that sets up DiscordUI for each conversation:

def create_discord_ui(ctx, llm_task_core, history_manager, ...):
    channel = get_discord_channel()  # from context
    author = get_discord_author()    # from context
    return DiscordUI(channel, author, ctx, llm_task_core, history_manager, ...)

llm_chat.set_ui_factory(create_discord_ui)

2. Start the Discord bot in a background task:

async def main():
    # Start Discord bot
    bot_task = asyncio.create_task(bot.start(DISCORD_BOT_TOKEN))
    
    # Run zrb (if needed)
    # ...
    
    await bot_task

3. Route Discord messages to the correct UI:

@bot.event
async def on_message(message):
    # Get or create conversation
    key = f"{message.channel.id}_{message.author.id}"
    if key not in _conversations:
        ui = create_ui_for_conversation(...)
        _conversations[key] = ui
        asyncio.create_task(ui.run_async())
    
    ui = _conversations[key]
    
    # Route message
    if ui.is_waiting_for_response():
        await ui.provide_ask_user_response(message.content)
    else:
        ui._submit_user_message(ui._llm_task, message.content)
"""
