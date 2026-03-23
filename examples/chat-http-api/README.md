# HTTP API UI Example

This example demonstrates how to create an HTTP REST API UI for LLM chat using `BaseUI`.

## Pattern: Polling

HTTP API uses a **polling** pattern:

```
┌─────────────────┐                    ┌─────────────────┐
│  HTTP Client     │                    │   HttpAPIUI     │
│  (curl/browser) │                    │   (BaseUI)      │
└────────┬────────┘                    └────────┬────────┘
         │                                      │
         │  POST /chat {message}                 │
         │ ──────────────────────────────────────>│
         │                                      │
         │  {"session_id": "abc123"}            │
         │ <─────────────────────────────────────│
         │                                      │
         │  GET /poll?session=abc123             │
         │ ──────────────────────────────────────>│
         │                                      │
         │  {"messages": [...], "current_question": "..."}
         │ <─────────────────────────────────────│
         │                                      │
         │  POST /input {response}               │
         │ ──────────────────────────────────────>│
         │                                      │
```

**Key characteristic**: Clients **poll** for messages and **post** inputs.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      HTTP API Server                         │
│                                                              │
│  Endpoints:                                                  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ POST /chat        - Start/continue conversation        │  │
│  │ GET  /poll        - Get pending messages               │  │
│  │ POST /input       - Provide input for ask_user()       │  │
│  │ GET  /status       - Get session status                │  │
│  └────────────────────────────────────────────────────────┘  │
│                            │                                 │
│                   ┌─────────▼─────────┐                      │
│                   │   SessionManager  │                      │
│                   │                   │                      │
│                   │  sessions: {      │                      │
│                   │   id1: {          │                      │
│                   │     ui: HttpAPIUI,│                      │
│                   │     output_queue, │                      │
│                   │     input_queue   │                      │
│                   │   }               │                      │
│                   │  }                │                      │
│                   └─────────┬─────────┘                      │
│                             │                                │
│                   ┌─────────▼─────────┐                      │
│                   │   LLMChatTask     │                      │
│                   └───────────────────┘                      │
└──────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
pip install aiohttp
```

### 2. Run the Server

```bash
cd examples/chat-http-api
python main.py
```

### 3. Use the API

**Start a conversation:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, how are you?"}'

# Response:
# {"session_id": "abc12345", "status": "started"}
```

**Poll for messages:**
```bash
curl "http://localhost:8000/poll?session=abc12345"

# Response:
# {
#   "session_id": "abc12345",
#   "messages": [
#     {"type": "output", "content": "Hello! I'm doing well...")}
#   ],
#   "current_question": null
# }
```

**When there's a question (tool approval):**
```bash
curl "http://localhost:8000/poll?session=abc12345"

# Response:
# {
#   "messages": [
#     {"type": "question", "content": "Approve tool call 'read_file'?"}
#   ],
#   "current_question": "Approve tool call 'read_file'?"
# }
```

**Provide input for the question:**
```bash
curl -X POST http://localhost:8000/input \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc12345", "response": "y"}'

# Response:
# {"status": "ok", "session_id": "abc12345"}
```

## API Reference

### POST /chat

Start a new conversation or continue an existing one.

**Request:**
```json
{
  "message": "Hello!",
  "session_id": "optional-existing-session"
}
```

**Response:**
```json
{
  "session_id": "abc12345",
  "status": "started" | "continued"
}
```

### GET /poll

Get pending messages for a session.

**Query Parameters:**
- `session` (required): Session ID

**Response:**
```json
{
  "session_id": "abc12345",
  "messages": [
    {"type": "output", "content": "...", "timestamp": "..."},
    {"type": "question", "content": "...", "timestamp": "..."}
  ],
  "current_question": "Approve?" | null
}
```

### POST /input

Provide input for `ask_user()` (tool approval).

**Request:**
```json
{
  "session_id": "abc12345",
  "response": "y"
}
```

**Response:**
```json
{
  "status": "ok",
  "session_id": "abc12345"
}
```

### GET /status

Get session status.

**Query Parameters:**
- `session` (required): Session ID

**Response:**
```json
{
  "session_id": "abc12345",
  "running": true,
  "current_question": "Approve?" | null,
  "pending_messages": 3
}
```

## Key Implementation Details

### 1. Session Management

```python
@dataclass
class SessionState:
    session_id: str
    ui: HttpAPIUI
    output_queue: asyncio.Queue
    input_queue: asyncio.Queue

_sessions: dict[str, SessionState] = {}
```

### 2. Output Queue for Polling

```python
def append_to_output(self, *values, sep=" ", end="\n"):
    message = {"type": "output", "content": content}
    self._output_queue.put_nowait(message)

async def get_pending_messages() -> list:
    messages = []
    while not self._output_queue.empty():
        messages.append(self._output_queue.get_nowait())
    return messages
```

### 3. Blocking ask_user()

```python
async def ask_user(self, prompt: str) -> str:
    # Put question in queue (poll shows it)
    self._output_queue.put_nowait({"type": "question", "content": prompt})
    
    # Wait for /input endpoint
    response = await self._input_queue.get()
    return response
```

## Comparison: HTTP vs WebSocket

| Feature | HTTP (Polling) | WebSocket |
|---------|----------------|------------|
| Connection | Stateless | Persistent |
| Messages | Poll manually | Push automatically |
| Complexity | Higher client | Higher server |
| Scalability | Better | Connection limits |
| Use case | REST APIs, SSE | Real-time apps |

## Use Cases

1. **REST API**: Expose LLM as a REST service
2. **Server-Sent Events (SSE)**: Combine with SSE for push notifications
3. **Testing**: Easy to test with curl/Postman
4. **Webhooks**: Combine with webhook callbacks

## Related Examples

- **chat-websocket**: Bidirectional real-time communication
- **chat-telegram**: Event-driven with bot polling
- **chat-discord**: Event-driven with Discord bot

## Files

| File | Purpose |
|------|--------|
| `main.py` | HttpAPIUI implementation |
| `README.md` | This file |