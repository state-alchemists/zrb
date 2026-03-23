# WebSocket UI Example

This example demonstrates how to create a WebSocket-based UI for LLM chat using `BaseUI`.

## Pattern: Request-Response

WebSocket uses a **request-response** pattern:

```
┌─────────────────┐                     ┌─────────────────┐
│  Browser/Client │                     │   WebSocketUI   │
│   (JavaScript)  │                     │   (BaseUI)      │
└────────┬────────┘                     └────────┬────────┘
         │                                       │
         │  1. Send message                      │
         │ ─────────────────────────────────────>│
         │                                       │
         │                   2. Process with LLM │
         │                                       │
         │  3. Receive response                  │
         │ <─────────────────────────────────────│
         │                                       │
         │  4. ask_user() blocks until input     │
         │ <─────────────────────────────────────│
         │                                       │
         │  5. Send response                     │
         │ ─────────────────────────────────────>│
         │                                       │
```

**Key characteristic**: `ask_user()` can **block** waiting for input.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    WebSocket Server                          │
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │
│  │ Client 1    │    │ Client 2    │    │ Client N    │       │
│  │ (WebSocket) │    │ (WebSocket) │    │ (WebSocket) │       │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘       │
│         │                  │                  │              │
│         └──────────────────┼──────────────────┘              │
│                            │                                 │
│                   ┌─────────▼─────────┐                      │
│                   │   WebSocketUI     │                      │
│                   │   (BaseUI)        │                      │
│                   │                   │                      │
│                   │  - ask_user()     │                      │
│                   │  - _input_queue   │                      │
│                   └─────────┬─────────┘                      │
│                             │                                │
│                   ┌─────────▼─────────┐                      │
│                   │   LLMChatTask     │                      │
│                   │   (AI Agent)      │                      │
│                   └───────────────────┘                      │
└──────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
pip install websockets
```

### 2. Run the Server

```bash
cd examples/chat-websocket
python main.py
```

### 3. Connect with a Client

**Python (websocket-client):**
```python
import asyncio
import websockets
import json

async def chat():
    async with websockets.connect('ws://localhost:8765') as ws:
        # Receive welcome
        msg = await ws.recv()
        print(json.loads(msg))
        
        # Send message
        await ws.send(json.dumps({
            "type": "chat",
            "content": "Hello, how are you?"
        }))
        
        # Receive response
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            print(f"[{data['type']}]: {data['content']}")
            
            if data['type'] == 'question':
                # Need to respond
                await ws.send(json.dumps({
                    "type": "response",
                    "content": "y"
                }))

asyncio.run(chat())
```

**JavaScript (Browser):**
```javascript
const ws = new WebSocket('ws://localhost:8765');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(`[${data.type}]:`, data.content);
    
    if (data.type === 'question') {
        // Need to respond
        ws.send(JSON.stringify({
            type: 'response',
            content: 'y'
        }));
    }
};

ws.onopen = () => {
    ws.send(JSON.stringify({
        type: 'chat',
        content: 'Hello!'
    }));
};
```

## Message Protocol

### Client → Server

| Type | Purpose | Example |
|------|---------|--------|
| `chat` | Regular chat message | `{"type": "chat", "content": "Hello"}` |
| `response` | Response to ask_user | `{"type": "response", "content": "y"}` |
| `command` | UI command | `{"type": "command", "content": "/help"}` |

### Server → Client

| Type | Purpose | Example |
|------|---------|--------|
| `output` | AI response | `{"type": "output", "content": "Hello!"}` |
| `question` | Waiting for input | `{"type": "question", "content": "Approve?"}` |
| `waiting` | Ready for input | `{"type": "waiting", "content": "..."}` |
| `error` | Error message | `{"type": "error", "content": "..."}` |
| `welcome` | Connection established | `{"type": "welcome", "content": "..."}` |

## Key Implementation Details

### 1. `ask_user()` Blocks

```python
async def ask_user(self, prompt: str) -> str:
    # Send prompt to client
    await self.ws.send(json.dumps({"type": "question", "content": prompt}))
    
    # BLOCK until client responds
    response = await self._input_queue.get()
    return response
```

### 2. Message Routing

```python
async def receive_messages():
    async for raw_message in self.ws:
        data = json.loads(raw_message)
        
        if data["type"] == "response":
            # Route to blocked ask_user
            await self._input_queue.put(data["content"])
        elif data["type"] == "chat":
            # Submit to LLM
            self._submit_user_message(self._llm_task, data["content"])
```

### 3. Connection Lifecycle

```python
async def run_async(self):
    # Start receiving messages
    receive_task = asyncio.create_task(receive_messages())
    
    try:
        while self._running:
            await asyncio.sleep(0.1)
    finally:
        receive_task.cancel()
```

## Comparison: WebSocket vs Event-Driven

| Feature | WebSocket (Request-Response) | Telegram/Discord (Event-Driven) |
|---------|------------------------------|--------------------------------|
| `ask_user()` | Blocks on queue | Non-blocking, callback-based |
| Message handling | Linear | Routed by type |
| Bot lifecycle | None | Polling/webhook setup |
| Complexity | Lower | Higher |

## Related Examples

- **chat-http-api**: REST API with polling
- **chat-telegram**: Event-driven with bot polling
- **chat-discord**: Event-driven with Discord bot

## Files

| File | Purpose |
|------|--------|
| `main.py` | WebSocketUI implementation |
| `README.md` | This file |