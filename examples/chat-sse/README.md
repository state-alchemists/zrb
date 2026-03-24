# SSE Chat Example

Server-Sent Events (SSE) for real-time LLM chat. No polling, no missed messages!

When you run `zrb llm chat` from this directory, it starts an HTTP server with SSE streaming.

## Architecture

```
┌──────────────┐     POST /chat      ┌──────────────┐     handle_incoming_message()     ┌──────────────┐
│    Client    │ ──────────────────► │  SSE Server  │ ─────────────────────────────────►│     LLM      │
│              │                     │              │                                    │              │
│              │     GET /stream     │              │         broadcast(SSE)            │              │
│              │ ◄────────────────── │◄─────────────│◄──────────────────────────────────│              │
└──────────────┘   (SSE stream)      └──────────────┘                                    └──────────────┘
```

**Key: `handle_incoming_message()` routes correctly:**
- If LLM is waiting on `get_input()` (e.g., asking a question) → unblocks it
- If LLM is idle → starts a new conversation turn

**SSE ensures no missed messages:**
- Client stays connected to `/stream`
- All output is broadcast in real-time
- Automatic keepalive prevents timeout

## Quick Start

```bash
# Terminal 1: Start the server
export OPENAI_API_KEY="your-key"
cd /path/to/zrb/examples/chat-sse
zrb llm chat

# Terminal 2: Connect to SSE stream (stays connected)
curl -N http://localhost:8000/stream

# Terminal 3: Send messages
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!"}'

# Continue conversation
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is 2+2?"}'
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SSE_HOST` | `localhost` | Server bind address |
| `SSE_PORT` | `8000` | Server port |

## API Endpoints

### POST /chat

Send a message to the LLM.

**Request:**
```json
{"message": "Hello!"}
```

**Response:**
```json
{"status": "sent", "message": "Hello!"}
```

### GET /stream

Server-Sent Events endpoint. Connect and receive all LLM output in real-time.

**Response Format:**
```
event: connected
data: {"status": "connected"}

data: "AI: Hello! How can I help you?"

data: "I'm thinking..."

data: "The answer is 42."
```

**Keep Connected:** The connection stays open. Keepalive comments (`: keepalive`) are sent every 30 seconds.

### GET /status

Check session status.

**Response:**
```json
{
  "waiting_for_input": false,
  "session_name": "random-session-name"
}
```

### GET /history

Get conversation history. Useful for resuming after disconnecting.

**Query Parameters:**
| Param | Default | Description |
|-------|---------|-------------|
| `session` | current | Session name to load |
| `format` | `text` | Output format: `text` or `json` |
| `max_length` | `10000` | Max characters (for text format) |

**Text Format Response:**
```
💬 14:30 >> Hello!
🤖 14:30 >>
  Hello! How can I help you?

💬 14:31 >> What is 2+2?
🤖 14:31 >>
  2 + 2 = 4.
```

**JSON Format Response:**
```json
{
  "session_name": "my-session",
  "message_count": 4,
  "messages": [
    {"kind": "request", "parts": [...]},
    {"kind": "response", "parts": [...]}
  ]
}
```

**Example - Get history after reconnect:**
```bash
# Get current session's history as text
curl http://localhost:8000/history

# Get specific session as JSON
curl "http://localhost:8000/history?session=my-session&format=json"
```

## How It Works

### EventDrivenUI + SSE Pattern

```python
class SSEUI(EventDrivenUI, BufferedOutputMixin):
    def __init__(self, server: SSEServer, **kwargs):
        super().__init__(**kwargs)
        BufferedOutputMixin.__init__(self, flush_interval=0.3)
        self.server = server
        server.set_ui(self)
    
    async def _send_buffered(self, text: str) -> None:
        """Broadcast buffered content to all SSE clients."""
        await self.server.broadcast(text)
    
    async def print(self, text: str) -> None:
        """Buffer output (called during streaming)."""
        self.buffer_output(text)
    
    async def start_event_loop(self) -> None:
        """Start the SSE server."""
        await self.server.start()
        await self.start_flush_loop()
        while True:
            await asyncio.sleep(3600)
```

### handle_incoming_message() Pattern

**The common pitfall**: External systems often send messages to `input_queue` directly, but this ONLY works when the LLM is blocked on `get_input()`. When LLM is idle, those messages are lost.

**The fix**: Use `handle_incoming_message()` instead:

```python
# ❌ WRONG - loses messages when LLM idle
ui.input_queue.put_nowait(message)

# ✅ CORRECT - routes to the right place
ui.handle_incoming_message(message)
```

This method checks `_waiting_for_input`:
- `True` → LLM is blocked on `get_input()`, put to `_input_queue`
- `False` → LLM is idle, start a new conversation turn

## Comparison with Other Patterns

| Pattern | Real-time? | Missed messages? | Complexity |
|---------|------------|------------------|------------|
| **SSE** (this) | ✅ Yes | ❌ No | Low |
| HTTP Polling | ❌ No | ⚠️ Yes | Medium |
| WebSocket | ✅ Yes | ❌ No | High |

**Why SSE over WebSocket:**
- Simpler protocol (HTTP-based)
- Automatic reconnection in browsers
- No need for bidirectional (we use POST for sending)
- Native JavaScript support (`EventSource`)

## Browser Example

```javascript
// Connect to SSE stream
const eventSource = new EventSource('http://localhost:8000/stream');

eventSource.onmessage = (event) => {
    const text = JSON.parse(event.data);
    console.log('Received:', text);
    // Add to your chat UI
    addMessageToUI(text);
};

eventSource.onerror = (error) => {
    console.error('SSE Error:', error);
    // Browser will auto-reconnect
};

// Send messages
async function sendMessage(text) {
    await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({message: text})
    });
}
```

## Session Management

This example uses a **single session** for simplicity. The LLM maintains conversation context across requests.

For multi-session support, you would need to:
1. Create multiple `SSEUI` instances (one per session)
2. Route requests using session IDs
3. Manage connection-per-session mapping