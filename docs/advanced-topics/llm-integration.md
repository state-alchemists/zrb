🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > LLM Integration

# LLM Integration (AI Assistant)

Zrb comes with a powerful, built-in AI assistant that can understand your codebase, perform actions on your behalf, and automate complex software engineering tasks.

---

## Table of Contents

- [Interactive Chat](#interactive-chat-zrb-llm-chat)
- [Programmatic Usage](#programmatic-usage-llmtask-and-llmchattask)
- [Custom Tools and Sub-agents](#custom-tools-and-sub-agents)
- [Context Management](#context-management)
- [Quick Reference](#quick-reference)

---

## Interactive Chat (`zrb llm chat`)

The primary way to interact with AI Assistant is through an interactive terminal user interface (TUI).

```bash
zrb llm chat "Can you help me refactor the user authentication service?"
```

This launches a full-screen chat application where you can have a conversation with the assistant.

### TUI Commands

| Command | Description |
|---------|-------------|
| `/q`, `/bye`, `/quit`, `/exit` | Exit the application |
| `/info`, `/help` | Show all available commands |
| `/compress`, `/compact` | Summarize conversation to free context |
| `/model <name>` | Switch LLM model (e.g., `/model openai:gpt-4o`) |
| `/yolo` or `/yolo <tools>` | Toggle auto-execute mode. With tool names (e.g., `/yolo Write,Edit`), selectively auto-approve only those tools |
| `/load <name>` | Load a named session |
| `/save <name>` | Save current session |
| `/attach <file_path>` | Attach a file to next message |
| `>` or `/redirect <file_path>` | Save last response to file |
| `!` or `/exec <shell_cmd>` | Execute shell command |

> 💡 **Tip:** Any `/command` that matches a loaded skill will be executed as a skill.

### Approval Policies

By default, Zrb prompts for confirmation before executing most tools. This is controlled by YOLO mode:

| Mode | Behavior |
|------|----------|
| **YOLO off** | All tools require confirmation |
| **YOLO on** | All tools auto-approved |
| **Selective YOLO** | Only specified tools auto-approved (e.g., `/yolo Write,Edit`) |

**Safe Command Policy:** The `Bash` tool automatically approves known-safe read-only commands (e.g., `ls`, `git status`, `cat`, `grep`) without requiring YOLO mode. Commands with dangerous shell metacharacters (`>`, `|`, `;`, `&&`) always require explicit approval.

---

## Programmatic Usage (`LLMTask` and `LLMChatTask`)

You can also integrate the LLM directly into your automated workflows using two specialized task types.

### `LLMTask` (Single-Shot)

Use `LLMTask` for single-shot requests where you need the LLM to process input and return a result without conversational history.

```python
from zrb import LLMTask, cli

summarize_task = cli.add_task(
    LLMTask(
        name="summarize",
        system_prompt="You are an expert summarizer.",
        message="Please summarize the following text: {ctx.input.text}"
    )
)
```

### `LLMChatTask` (Conversational)

Use `LLMChatTask` to create your own fully customizable, interactive chat interfaces.

```python
from zrb import LLMChatTask, cli, StrInput

custom_chat = cli.add_task(
    LLMChatTask(
        name="custom-chat",
        ui_greeting="Hello from your custom assistant!",
        input=[StrInput(name="user_message", ...)],
        message="{ctx.input.user_message}"
    )
)
```

### Comparison

| Feature | `LLMTask` | `LLMChatTask` |
|---------|-----------|---------------|
| **Use case** | Single-shot processing | Interactive chat |
| **History** | None | Persistent session |
| **TUI** | No | Yes |
| **Custom tools** | Yes | Yes |

---

## Custom Tools and Sub-agents

You can extend the assistant's capabilities with your own Python functions.

### Custom Python Tools

Any Python function can be registered as a tool. The assistant automatically understands the function's purpose from its docstring and arguments.

```python
def get_weather(location: str) -> str:
    """Gets the current weather for a given location."""
    # ... your implementation ...

my_chat_task.add_tool(get_weather)
```

### Sub-agents

Zrb can automatically discover and manage sub-agents defined in JSON or YAML files within an `agents/` directory. The primary assistant can then delegate complex tasks to these specialized agents using the built-in `delegate_to_agent` tool.

> 💡 **Benefit:** Sub-agents isolate context and keep the main conversation history clean.

---

## Context Management

The AI Assistant is designed for long-running, complex tasks and has a sophisticated context management system.

### Two-Tier Summarization

| Level | Trigger | Action |
|-------|---------|--------|
| **Message-level** | Single tool output too large | Summarize before adding to history |
| **Conversational** | Overall history grows too large | Compress older messages to `<state_snapshot>` |

### 30% Retention Policy

When summarization triggers, the system:

| Action | Description |
|--------|-------------|
| Compress | Oldest 70% → state snapshot |
| Retain | Most recent 30% verbatim |
| Preserve | Tool call/return pairs never separated |
| Split | At conversation turn boundaries |

### Journal System

For persistent, long-term memory, Zrb uses a journal system—a directory of Markdown files (default: `~/.zrb/llm-notes/`) where the assistant can keep notes. The `index.md` file is automatically included in every context.

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `zrb llm chat` | Start interactive chat |
| `zrb llm chat "message"` | Start with initial message |

| Task Type | Import | Use Case |
|-----------|--------|----------|
| `LLMTask` | `from zrb import LLMTask` | Single processing |
| `LLMChatTask` | `from zrb import LLMChatTask` | Interactive chat |

---