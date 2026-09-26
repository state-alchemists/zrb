🔖 [Documentation Home](../../README.md) > [LLM](./) > LLM Integration

# LLM Integration (AI Assistant)

Zrb comes with a powerful, built-in AI assistant that can understand your codebase, perform actions on your behalf, and automate complex software engineering tasks.

This page covers the end-user surface: the interactive TUI and embedding `LLMTask`/`LLMChatTask` in your own project. To register custom tools, delegate to sub-agents, override model capabilities, or tune context management, see [Extending the LLM](extending-the-llm.md). Deciding between zrb and a standalone coding agent (Claude Code, opencode, DeepSeek Harness, Pi)? See [Choosing Between Agent Harnesses](harness-comparison.md).

---

## Table of Contents

- [Interactive Chat](#interactive-chat-zrb-llm-chat)
  - [TUI Commands](#tui-commands)
  - [Session Token Tracking](#session-token-tracking)
  - [Approval Policies](#approval-policies)
  - [Troubleshooting: Voice & Photo](#troubleshooting-voice--photo)
- [Permission Policy System](./permission-policy.md)
- [Sandbox (Filesystem Containment)](./sandbox.md)
- [Plan Mode](./plan-mode.md)
- [Programmatic Usage](#programmatic-usage-llmtask-and-llmchattask)
- [Quick Reference](#quick-reference)
- [Extending the LLM](extending-the-llm.md) — built-in tools, custom tools, sub-agents, model capabilities, context management

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
| `/attach <file_path>` | Attach a file to next message (capped by `LLM_MAX_ATTACHMENT_BYTES`, default 20MB; content is sniffed against its extension) |
| `/photo [device]` | Capture a photo from the camera and attach it to the next message (device is optional; auto-detected per platform) |
| `>` or `/redirect` (bare) | Copy last AI response to clipboard |
| `>` or `/redirect <file_path>` | Save last AI response to a file |
| `/copy` (bare) | Copy full conversation transcript to clipboard |
| `/copy <file_path>` | Save full conversation transcript to file |
| `!` or `/exec <shell_cmd>` | Execute shell command |
| `/btw <text>` | Inject a side note for the next turn without sending it as a message (runs while the assistant is thinking) |
| `/plan` | Toggle [Plan Mode](./plan-mode.md) (read-only discovery) |
| `/rewind [n\|sha]` | List or restore filesystem + history [snapshots](../configuration/llm-config.md#6-rewind--snapshots) (on by default; `ZRB_LLM_ENABLE_REWIND`) |
| `/voice` | Toggle push-to-talk voice dictation on/off (enabled automatically when `vosk` is installed and `ZRB_LLM_VOICE_ENABLED` is unset; see [Voice Dictation](../configuration/llm-config.md#23-voice-dictation)) |

> 💡 **Tip:** Any `/command` that matches a loaded skill will be executed as a skill.
>
> The token(s) that trigger each command are configurable — see [Slash Command Aliases](../configuration/llm-config.md#17-slash-command-aliases).

### Session Token Tracking

The TUI status bar tracks accumulated LLM token usage across all requests in a session. After the first LLM request completes, the status bar displays a token count like:

```
💸 1.5k in · 34 out
```

The counters reset whenever you switch conversations via `/load`, since past sessions' spend is not persisted. Tokens are tracked per-UI instance — in a `MultiUI` setup each child UI maintains its own totals.

There are no configuration knobs for this feature; it always appears (non-zero after the first request) and uses the theme's `FAINT` style.

### Approval Policies

By default, Zrb prompts for confirmation before executing most tools. This is controlled by YOLO mode and the [Permission Policy](./permission-policy.md) system:

| Mode | Behavior |
|------|----------|
| **YOLO off** | All tools require confirmation |
| **YOLO on** | All tools auto-approved |
| **Selective YOLO** | Only specified tools auto-approved (e.g., `/yolo Write,Edit`) |
| **Permission Policy** | Fine-grained `ALLOW`/`DENY`/`ASK` rules that can override YOLO |
| **Plan Mode** | Strict read-only mode for discovery. See [Plan Mode](./plan-mode.md) |

**Safe Command Policy:** The `Shell` tool automatically approves known-safe read-only commands (e.g., `ls`, `git status`, `cat`, `grep`) without requiring YOLO mode. Commands with dangerous shell metacharacters (`>`, `|`, `;`, `&`, `` ` ``, `$()`, `\n`, `\r`) always require explicit approval. Known-safe prefixes include `ls`, `cat`, `grep`, `git status`, `printenv`, and similar read-only commands — note that bare `env` is intentionally excluded as `env FOO=1 rm -rf x` can execute arbitrary commands.

### Troubleshooting: Voice & Photo

`/voice` and `/photo` depend on OS-level microphone/camera access, so failures are usually platform setup, not a zrb bug. Symptom-by-symptom fixes (macOS/Linux/Windows/WSL/Termux, including building a WSL2 kernel with camera support) are in [Voice & Photo Troubleshooting](voice-photo-troubleshooting.md).

---

## Programmatic Usage (`LLMTask` and `LLMChatTask`)

You can also integrate the LLM directly into your automated workflows using two specialized task types. Both accept `message`, `system_prompt`, and `prompt_manager` as values, templates, callables, or sections — see the full guide at **[Programming the Prompt](programming-the-prompt.md)** for examples of each rung.

### `LLMTask` (Single-Shot)

Use `LLMTask` for single-shot requests where you need the LLM to process input and return a result without conversational history.

```python
from zrb import LLMTask, Tpl, cli

summarize_task = cli.add_task(
    LLMTask(
        name="summarize",
        system_prompt="You are an expert summarizer.",
        message=Tpl("Please summarize the following text: {ctx.input.text}")
    )
)
```

### `LLMChatTask` (Conversational)

Use `LLMChatTask` to create your own fully customizable, interactive chat interfaces.

```python
from zrb import LLMChatTask, Tpl, cli, StrInput
from zrb.llm.ui import UIConfig

custom_chat = cli.add_task(
    LLMChatTask(
        name="custom-chat",
        ui_config=UIConfig(greeting="Hello from your custom assistant!"),
        input=[StrInput(name="user_message", ...)],
        message=Tpl("{ctx.input.user_message}")
    )
)
```

> 📖 **API Reference:** For the full `LLMChatTask` builder API — tools, guidance, hooks, policies, triggers, and custom commands — see the [LLMChatTask API Reference](../task-types/llmchat-task.md).

### Comparison

`LLMTask` is single-shot with no history and no TUI; `LLMChatTask` is an interactive chat with a persistent session. Both take custom tools. Full feature matrix: [LLMChatTask API Reference → Comparison with LLMTask](../task-types/llmchat-task.md#comparison-with-llmtask).

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

🔖 [Documentation Home](../../README.md) > [LLM](./) > LLM Integration
