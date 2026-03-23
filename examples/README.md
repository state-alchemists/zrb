# Examples Overview

This directory contains examples showing how to extend `zrb llm chat` for different backends.

## Example Complexity Levels

| Example | Lines | Base Class | Description |
|---------|-------|------------|-------------|
| `chat-minimal-ui` | ~40 | `SimpleUI` | **Easiest** - Just 2 methods to implement |
| `chat-telegram` | ~90 | `EventDrivenUI` | Telegram bot with inline button approvals |
| `chat-discord` | ~90 | `EventDrivenUI` | Discord bot with reaction approvals |
| `chat-websocket` | ~50 | `PollingUI` | WebSocket server for LLM chat |
| `chat-http-api` | ~60 | `PollingUI` | HTTP REST API for LLM chat |
| `chat-telegram-cli` | ~300 | `BaseUI` | **Advanced** - Multiplexed UI (CLI + Telegram) |

## Quick Start: Minimal UI (Recommended)

The simplest way to create a custom UI backend:

```python
from zrb.builtin.llm.chat import llm_chat
from zrb.llm.app import SimpleUI, create_ui_factory
import asyncio

class MyUI(SimpleUI):
    """Just implement 2 methods!"""

    def print(self, text: str) -> None:
        print(text, end="", flush=True)

    async def get_input(self, prompt: str) -> str:
        if prompt:
            print(f"❓ {prompt}")
        return await asyncio.to_thread(input, "You> ")

# Register - ONE line!
llm_chat.set_ui_factory(create_ui_factory(MyUI))
```

## Extension Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│ Level 1: SimpleUI (RECOMMENDED for beginners)                   │
│         - Implement just 2 methods: print(), get_input()        │
│         - For basic backends (CLI, simple WebSocket)            │
├─────────────────────────────────────────────────────────────────┤
│ Level 2: EventDrivenUI (for event-driven backends)              │
│         - Implement: print(), start_event_loop()                │
│         - Call handle_incoming_message() on events              │
│         - For Telegram, Discord, WhatsApp                       │
├─────────────────────────────────────────────────────────────────┤
│ Level 3: PollingUI (for polling backends)                       │
│         - Implement: print()                                    │
│         - Use built-in output_queue/input_queue                 │
│         - For HTTP API, WebSocket polling                       │
├─────────────────────────────────────────────────────────────────┤
│ Level 4: BaseUI (full control, advanced)                        │
│         - Implement 5+ methods                                  │
│         - For maximum flexibility                               │
└─────────────────────────────────────────────────────────────────┘
```

## Code Size Comparison

| Implementation | Lines of Code | Reduction vs BaseUI |
|---------------|---------------|---------------------|
| BaseUI (original) | 180+ | - |
| SimpleUI | 20-40 | **78% smaller** |
| EventDrivenUI | 40-80 | **56% smaller** |
| PollingUI | 30-50 | **72% smaller** |

## Key Files

- `src/zrb/llm/app/__init__.py` - Exports all UI classes
- `src/zrb/llm/app/simple_ui.py` - Simplified UI classes
- `src/zrb/llm/app/base_ui.py` - Full-featured base class
- `src/zrb/llm/app/ui.py` - Default terminal UI

## Running Examples

```bash
# Set up environment
export OPENAI_API_KEY="your-key"

# Use minimal UI
cd examples/chat-minimal-ui
zrb llm chat

# Use Telegram
export TELEGRAM_BOT_TOKEN="your-token"
export TELEGRAM_CHAT_ID="your-chat-id"
cd examples/chat-telegram
zrb llm chat
```

## See Also

- [Extension Guide](../docs/extension-guide.md) - Detailed documentation
- [Approval Channels](../src/zrb/llm/approval/) - Tool confirmation interfaces