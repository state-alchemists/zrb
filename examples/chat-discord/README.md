# Discord UI Example

This example demonstrates how to create a Discord bot UI for LLM chat using `BaseUI`.

## Pattern: Event-Driven

Discord uses an **event-driven** pattern:

```
┌─────────────────┐                    ┌─────────────────┐
│  Discord User    │                    │   DiscordUI     │
│  (Chat Client)  │                    │   (BaseUI)      │
└────────┬────────┘                    └────────┬────────┘
         │                                      │
         │  Message Event                        │
         │ ──────────────────────────────────────>│
         │                                      │
         │                    on_message() routes:
         │                    - ask_user response?
         │                    - command?
         │                    - chat message?
         │                                      │
         │  Discord Message (output)            │
         │ <─────────────────────────────────────│
         │                                      │
         │  Reaction (approval)                 │
         │ ──────────────────────────────────────>│
         │                                      │
```

**Key characteristic**: `ask_user()` **cannot block** - must use queues and routing.

## Key Differences from Request-Response

| Feature | Request-Response (WebSocket, HTTP) | Event-Driven (Discord, Telegram) |
|---------|-----------------------------------|----------------------------------|
| `ask_user()` | Blocks on queue | Returns immediately |
| Message handling | Linear flow | Routed by type |
| Bot lifecycle | None needed | Polling/webhook setup |
| State | Simple | Per channel/user |
| Complexity | Lower | Higher |

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      Discord Bot                              │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ on_message(message):                                     │  │
│  │   - Check if response to ask_user (route to queue)     │  │
│  │   - Check if command (process commands)                │  │
│  │   - Otherwise, route to _submit_user_message()        │  │
│  └────────────────────────────────────────────────────────┘  │
│                            │                                  │
│                   ┌─────────▼─────────┐                       │
│                   │ Message Router      │                       │
│                   │                   │                       │
│                   │ conversations: {   │                       │
│                   │   channel_user1: {  │                       │
│                   │     ui: DiscordUI,  │                       │
│                   │     waiting: false ║                      │
│                   │   },               │                       │
│                   │   channel_user2: {  │                       │
│                   │     ui: DiscordUI,  │                       │
│                   │     waiting: true   │                       │
│                   │   }                │                       │
│                   │ }                  │                       │
│                   └─────────┬─────────┘                       │
│                             │                                  │
│                   ┌─────────▼─────────┐                       │
│                   │   DiscordUI        │                       │
│                   │   (BaseUI)         │                       │
│                   │                   │                       │
│                   │  - ask_user_queue │                       │
│                   │  - channel.send() │                       │
│                   └─────────┬─────────┘                       │
│                             │                                  │
│                   ┌─────────▼─────────┐                       │
│                   │   LLMChatTask      │                       │
│                   └───────────────────┘                       │
└──────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
pip install discord.py
```

### 2. Create a Discord Bot

1. Go to https://discord.com/developers/applications
2. Create a "New Application"
3. Go to "Bot" and click "Add Bot"
4. Copy the bot token
5. Enable "Message Content Intent" under "Privileged Gateway Intents"
6. Invite the bot to your server:
   - Go to "OAuth2" → "URL Generator"
   - Select "bot" scope
   - Select permissions: Send Messages, Read Message History
   - Copy the invite link and open it

### 3. Run the Bot

```bash
# Set your bot token
export DISCORD_BOT_TOKEN="your-bot-token-here"

# Optionally restrict to a specific channel
export DISCORD_CHANNEL_ID="123456789"

# Run
zrb llm chat
```

### 4. Use in Discord

```
User: !start
Bot: 🤖 Starting new conversation...

User: Hello, how are you?
Bot: Hello! I'm doing well, thank you for asking...

User: !help
Bot: 🤖 ZrbBot Commands
     !start - Start a conversation
     !stop - End the conversation
     !yolo - Toggle auto-approve mode
     Chat  - Just send a message to chat!

User: !stop
Bot: 👋 Conversation ended.
```

## Message Routing

The critical part of event-driven backends is **message routing**:

```python
@bot.event
async def on_message(message: discord.Message):
    # Ignore bot messages
    if message.author == bot.user:
        return
    
    # Get conversation state
    conv_key = f"{message.channel.id}_{message.author.id}"
    if conv_key not in _conversations:
        # New conversation
        _conversations[conv_key] = ConversationState(...)
    
    conv = _conversations[conv_key]
    
    # ROUTE THE MESSAGE:
    
    # 1. Is this a response to ask_user?
    if conv.ui and conv.ui.is_waiting_for_response():
        await conv.ui.provide_ask_user_response(message.content)
        return
    
    # 2. Is this a command?
    if message.content.startswith('!'):
        await bot.process_commands(message)
        return
    
    # 3. It's a chat message
    if conv.ui:
        conv.ui._submit_user_message(conv.ui._llm_task, message.content)
```

## ask_user() Pattern

```python
async def ask_user(self, prompt: str) -> str:
    # 1. Send question to Discord
    message = await self.channel.send(f"❓ {prompt}")
    
    # 2. Mark that we're waiting
    self._waiting_for_response = True
    self._current_question_id = message.id
    
    try:
        # 3. Wait for response (message handler will put it here)
        response = await self._ask_user_queue.get()
        return response
    finally:
        self._waiting_for_response = False
        self._current_question_id = None
```

The message handler routes responses:

```python
if conv.ui.is_waiting_for_response():
    await conv.ui.provide_ask_user_response(message.content)
```

## Conversation State

Each channel/user combination needs its own state:

```python
class ConversationState:
    channel_id: int
    user_id: int
    ui: DiscordUI | None
    waiting_for_ask_user: bool
    current_question_id: int | None

conversations: dict[str, ConversationState] = {}
# Key: "{channel_id}_{user_id}"
```

## Discord-Specific Considerations

### 1. Message Chunking

Discord has a 2000 character limit:

```python
async def send_discord_message(self, content: str):
    if len(content) <= 1900:
        await self.channel.send(content)
    else:
        # Split into multiple messages
        for chunk in split_by_newlines(content, max_length=1900):
            await self.channel.send(chunk)
```

### 2. Embeds for Formatting

Use Embeds for better visualization:

```python
embed = discord.Embed(
    title="🤖 Response",
    description=response,
    color=discord.Color.blue()
)
await self.channel.send(embed=embed)
```

### 3. Reactions for Approvals

```python
@bot.event
async def on_raw_reaction_add(payload):
    if payload.emoji.name == '✅':
        # Approve tool
        await approve_tool(payload)
    elif payload.emoji.name == '❌':
        # Deny tool
        await deny_tool(payload)
```

### 4. Rate Limiting

Discord has rate limits:

```python
import asyncio

# Don't send too fast
async def rate_limited_send(channel, content):
    await asyncio.sleep(0.5)  # Brief pause
    await channel.send(content)
```

## Comparison with Other Backends

| Backend | Pattern | ask_user() | Complexity |
|---------|---------|-----------|----------|
| Terminal | Blocking | Block on input | Lowest |
| WebSocket | Request-Response | Block on queue | Medium |
| HTTP API | Polling | Block on queue | Medium |
| Discord | Event-Driven | Queue + routing | Higher |
| Telegram | Event-Driven | Queue + routing | Higher |

## Related Examples

- **chat-telegram**: Similar event-driven pattern
- **chat-websocket**: Request-response pattern
- **chat-http-api**: Polling pattern

## Files

| File | Purpose |
|------|--------|
| `zrb_init.py` | DiscordUI implementation |
| `README.md` | This file |