# WhatsApp UI Example

This example demonstrates how to create a WhatsApp Business bot UI for LLM chat using `BaseUI`.

## Pattern: Event-Driven with Webhooks

WhatsApp uses an **event-driven webhook** pattern:

```
┌─────────────────┐                    ┌─────────────────┐
│  WhatsApp User  │                    │   WhatsAppUI    │
│    (Phone)      │                    │    (BaseUI)     │
└────────┬────────┘                    └────────┬────────┘
         │                                      │
         │  1. Send message                     │
         │ ────────────────────────────────────>│
         │         (via Twilio webhook)         │
         │                                      │
         │              2. Route to handler     │
         │                                      │
         │  3. Send response (Twilio API)       │
         │ ◄────────────────────────────────────│
         │                                      │
```

**Key characteristic**: Webhooks must respond **quickly** (within 15 seconds).

## Why Twilio?

The WhatsApp Business API requires:
- Business verification
- Approved templates
- Per-conversation pricing

[Twilio's WhatsApp API](https://www.twilio.com/whatsapp) simplifies this:
- Easy setup (no business verification for testing)
- Same API as SMS
- Good documentation
- Sandbox mode for testing

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                        Your Server                             │
│                                                                │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ aiohttp Server (Webhook)                                  │ │
│  │                                                           │ │
│  │  POST /whatsapp                                           │ │
│  │    - Parse Twilio webhook                                 │ │
│  │    - Route to session                                     │ │
│  │    - Respond quickly (<15s)                               │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                 │
│                    ┌─────────▼──────────┐                      │
│                    │  Session Manager   │                      │
│                    │                    │                      │
│                    │ sessions: {        │                      │
│                    │   "+1234567890": { │                      │
│                    │     ui: WhatsAppUI,│                      │
│                    │     waiting: true  │                      │
│                    │   }                │                      │
│                    │ }                  │                      │
│                    └─────────┬──────────┘                      │
│                              │                                 │
│                    ┌─────────▼──────────┐                      │
│                    │   WhatsAppUI       │                      │
│                    │    (BaseUI)        │                      │
│                    │                    │                      │
│                    └─────────┬──────────┘                      │
│                              │                                 │
│                    ┌─────────▼──────────┐                      │
│                    │   LLMChatTask      │                      │
│                    └────────────────────┘                      │
└────────────────────────────────────────────────────────────────┘
         │
         │ Twilio API
         ▼
┌────────────────────────────────────────────────────────────────┐
│                        Twilio Cloud                            │
│                                                                │
│  - Receives WhatsApp message                                   │
│  - Sends webhook to your server                                │
│  - Delivers your response via WhatsApp                         │
└────────────────────────────────────────────────────────────────┘
         │
         │ WhatsApp Network
         ▼
┌────────────────────────────────────────────────────────────────┐
│                        WhatsApp User                           │
│                                                                │
│  Phone with WhatsApp installed                                 │
└────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
pip install aiohttp twilio
```

### 2. Set Up Twilio

1. Create a [Twilio account](https://www.twilio.com/try-twilio)
2. Go to [Twilio Console](https://www.twilio.com/console)
3. Note your Account SID and Auth Token
4. Set up WhatsApp Sandbox:
   - Go to Messaging → Try it out → Send a WhatsApp message
   - Follow instructions to join the sandbox

### 3. Configure Environment

```bash
export TWILIO_ACCOUNT_SID="your-account-sid"
export TWILIO_AUTH_TOKEN="your-auth-token"
export TWILIO_PHONE_NUMBER="whatsapp:+14155238886"  # Sandbox number
export WEBHOOK_URL="https://your-domain.com"  # Or ngrok URL
```

### 4. Run Locally with ngrok

```bash
# Install ngrok: https://ngrok.com/

# Start your server
cd examples/chat-whatsapp
python zrb_init.py

# In another terminal, start ngrok
ngrok http 8080

# Set your webhook URL
export WEBHOOK_URL="https://your-ngrok-url.ngrok.io"
```

### 5. Configure Twilio Webhook

1. Go to [Twilio Console → Phone Numbers](https://www.twilio.com/console/phone-numbers)
2. Select your WhatsApp-enabled number
3. Set webhook URL: `https://your-domain.com/whatsapp`
4. Method: POST

### 6. Use in WhatsApp

```
You: hello
Bot: Hello! I'm ZrbBot. How can I help you today?

You: What's the weather?
Bot: I don't have access to real-time weather data, but I can help
     you with other questions!

Bot: ❓ Question
     Would you like me to search for weather information?
     
     _Reply with your response._

You: yes
Bot: Great! Let me search for that...
```

## Webhook Handler

The webhook handler must respond quickly:

```python
async def handle_whatsapp_webhook(request: web.Request) -> web.Response:
    # Parse data
    data = await request.post()
    from_number = data.get("From", "")  # "whatsapp:+1234567890"
    message_body = data.get("Body", "")
    
    # Get session
    phone_number = from_number.replace("whatsapp:", "").strip()
    session = get_or_create_session(phone_number)
    
    # Route message quickly
    if session.ui and session.ui.is_waiting_for_response():
        # Response to ask_user
        asyncio.create_task(
            session.ui.provide_ask_user_response(message_body)
        )
    elif session.ui:
        # Regular message
        session.ui._submit_user_message(session.ui._llm_task, message_body)
    
    # Respond quickly (within 15 seconds!)
    response = MessagingResponse()
    return web.Response(text=str(response), content_type="application/xml")
```

## ask_user() Pattern

```python
async def ask_user(self, prompt: str) -> str:
    # 1. Send question via Twilio API
    question_text = f"❓ *Question*\n\n{prompt}\n\n_Reply with your response._"
    await self.send_whatsapp_message(question_text)
    
    # 2. Mark waiting state
    self._waiting_for_response = True
    
    try:
        # 3. Wait for webhook to provide response
        response = await self._ask_user_queue.get()
        return response
    finally:
        self._waiting_for_response = False
```

The webhook routes responses:

```python
if session.ui.is_waiting_for_response():
    await session.ui.provide_ask_user_response(message_body)
```

## Session Management

Each phone number needs its own session:

```python
@dataclass
class WhatsAppSession:
    phone_number: str
    ui: WhatsAppUI | None = None
    ask_user_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    waiting_for_response: bool = False

sessions: dict[str, WhatsAppSession] = {}
# Key: phone number (normalized)
```

## WhatsApp-Specific Considerations

### 1. Message Length

WhatsApp has a ~1600 character limit:

```python
async def send_whatsapp_message(self, content: str):
    max_length = 1500
    if len(content) <= max_length:
        await self.send(content)
    else:
        # Split into multiple messages
        for chunk in split_by_newlines(content, max_length):
            await self.send(chunk)
```

### 2. Formatted Messages

Use WhatsApp formatting:

```python
# Bold: *text*
# Italic: _text_
# Code: ```text```

message = """📋 *Options*

• Option 1: First choice
• Option 2: Second choice

_Reply with the number._"""
```

### 3. Rate Limiting

Twilio has rate limits:

```python
# Don't send too fast
import asyncio

async def send_with_rate_limit(messages: list[str]):
    for msg in messages:
        await self.send_whatsapp_message(msg)
        await asyncio.sleep(1)  # 1 second between messages
```

## Comparison with Other Backends

| Feature | WhatsApp | Discord | Telegram |
|---------|----------|---------|----------|
| Pattern | Webhook | Polling | Polling/Webhook |
| Response time | <15 seconds | No limit | No limit |
| Auth | Twilio | Bot token | Bot token |
| Local testing | ngrok | Direct | Direct |
| Message limit | ~1600 chars | ~2000 chars | ~4096 chars |

## Local Testing

ngrok creates a public URL for your local server:

```bash
# Terminal 1: Start server
python zrb_init.py

# Terminal 2: Start ngrok
ngrok http 8080

# Now your webhook is accessible at:
# https://your-ngrok-url.ngrok.io/whatsapp
```

## Related Examples

- **chat-telegram**: Similar event-driven pattern
- **chat-discord**: Similar event-driven pattern
- **chat-http-api**: Polling pattern

## Files

| File | Purpose |
|------|--------|
| `zrb_init.py` | WhatsAppUI implementation |
| `README.md` | This file |