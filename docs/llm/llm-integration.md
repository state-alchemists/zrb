🔖 [Documentation Home](../README.md) > [LLM](./) > LLM Integration

# LLM Integration (AI Assistant)

Zrb comes with a built-in AI assistant that can read your codebase, perform actions on your behalf, and carry out multi-step software engineering tasks.

This page covers the end-user surface: the interactive TUI and embedding `LLMTask`/`LLMChatTask` in your own project. To register custom tools, delegate to sub-agents, override model capabilities, or tune context management, see [Extending the LLM](extending-the-llm.md). Deciding between zrb and a standalone coding agent (Claude Code, opencode, DeepSeek Harness, Pi)? See [Choosing Between Agent Harnesses](harness-comparison.md).

---

## Table of Contents

- [Interactive Chat](#interactive-chat-zrb-llm-chat)
  - [TUI Commands](#tui-commands)
  - [Queued Messages](#queued-messages)
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
| `/q`, `:q`, `/bye`, `/quit`, `/exit` | Exit the application |
| `/info`, `/help` | Show all available commands |
| `/compress`, `/compact` | Summarize conversation to free context |
| `/model <name>` | Switch LLM model (e.g., `/model openai:gpt-4o`) |
| `/set <name> <value>` | Change a setting for the rest of the process, e.g. `/set LLM_SHOW_TOOL_CALL_RESULT on`. Any `CFG` field settable from Python is accepted (name without the `ZRB_` prefix, case-insensitive); Tab completes names, and values with model names, `on`/`off`, or the current value. `/set model`, `/set small_model` and `/set multimodal_model` switch that model live, like `/model`. Nothing is written to disk |
| `/yolo` or `/yolo <tools>` | Toggle auto-execute mode. With tool names (e.g., `/yolo Write,Edit`), selectively auto-approve only those tools |
| `/load <name>`, `/resume <name>` | Load a named session, and re-register its saved sub-agent transcripts as idle sessions you can message |
| `/save <name>` | Save current session |
| `/attach <file_path>` | Attach a file to next message (capped by `LLM_MAX_ATTACHMENT_BYTES`, default 20MB; content is sniffed against its extension) |
| `/photo [device]`, `/p [device]` | Capture a photo from the camera and attach it to the next message (device is optional and tab-completes; auto-detected per platform) |
| `>` or `/redirect` (bare) | Copy last AI response to clipboard |
| `>` or `/redirect <file_path>` | Save last AI response to a file |
| `/copy` (bare) | Copy full conversation transcript to clipboard |
| `/copy <file_path>` | Save full conversation transcript to file |
| `!` or `/exec <shell_cmd>` | Execute shell command |
| `/btw <question>` | Ask a side question answered by a separate agent that sees the conversation but has **no tools** — it cannot read a file or run a command, so it answers from what is already in context. The exchange is not saved to history. Works while the assistant is thinking |
| `/plan` | Toggle [Plan Mode](./plan-mode.md) (read-only discovery) |
| `/rewind [n\|sha]` | List or restore filesystem + history [snapshots](../configuration/llm-config.md#6-rewind--snapshots) (on by default; `ZRB_LLM_ENABLE_REWIND`) |
| `/voice`, `/v` | Record speech: a pause or `/voice` again stops, and the transcript lands in the input box. Needs `zrb[voice]` |
| `/handsfree` | Switch hands-free voice input on or off: every utterance becomes a turn, or answers the pending approval |
| `/speech` | Switch reading replies aloud on or off |

> 💡 **Tip:** Any `/command` that matches a loaded skill will be executed as a skill.
>
> The token(s) that trigger each command are configurable — see [Slash Command Aliases](../configuration/llm-config.md#17-slash-command-aliases). `/photo`, `/voice`, `/handsfree` and `/speech` come from [Voice and camera](voice-camera.md) and are configured there.

### Recalling Previous Messages

With nothing queued, `↑` in the input box walks back through messages you sent before, newest first: the user messages of the conversation you loaded (`/load`, or `--session` at startup), then every message you have submitted in any session. `↓` walks forward and finally restores what you were typing.

The cross-session list is kept in `ZRB_LLM_PREVIOUS_MESSAGE_HISTORY_DIR` (default `~/.zrb/llm-previous-message-history/`), capped at `ZRB_LLM_PREVIOUS_MESSAGE_HISTORY_MAX_ENTRIES` (default 1000; `0` keeps all). Writing it is best-effort: an unwritable directory never breaks a turn.

### Queued Messages

A message submitted while the assistant is thinking does not interrupt the turn. It waits in the queue, and runs when the turn finishes. What is waiting is listed above the input box, oldest first, with the one recalled for editing marked `▸`:

```text
 📥 2 queued · ↑ to edit
  1. fix the parser bug
 ▸2. and run the tests
```

| Key | What it does |
|-----|--------------|
| `↑` | Recall the newest queued message into the input box. Press it again to walk to older ones |
| `↓` | Walk back toward the newest, then restore whatever you were typing before the first recall |
| `Enter` | Replace the queued message with the edited text, in place — rather than submitting a new one |
| `Ctrl+X` | Drop the recalled message: it leaves the queue and its echoed line is taken out of every transcript. The input goes back to whatever you were typing before the recall |

The echoed `💬` line stays in the transcript above, so the whole of a queued message is always readable; the panel repeats only its first line. A multi-line paste in a terminal without bracketed paste arrives as one submit per Enter keystroke: lines submitted within `ZRB_LLM_UI_PASTE_MERGE_WINDOW` (default 100 ms) of a still-queued message are appended to it, so the model reads one message instead of a turn per line.

`Ctrl+X` reaches every transcript. In a `MultiUI` — the terminal plus a Telegram bot, say — the queue entry is shared but each UI keeps its own echo, so all of them lose the line; if the message's turn started while you had it recalled, it is left running and only the recall is dropped. Either way the input goes back to your pre-recall draft, so a recalled message you dropped cannot be sent again by a later `Enter`.

### Session Token Tracking

The TUI status bar tracks accumulated LLM token usage across all requests in a session. After the first LLM request completes, the status bar displays a token count like:

```
💸 1.5k in · 34 out
```

When the provider reports them, cached input tokens (`· 1.2k cached`) and the current context size (`· 🧠 3.4k ctx`) are appended.

The counters reset whenever you switch conversations via `/load`, since past sessions' spend is not persisted. Tokens are tracked per-UI instance — in a `MultiUI` setup each child UI maintains its own totals.

There are no configuration knobs for this feature; it always appears (non-zero after the first request) and uses the theme's `FAINT` style.

While the assistant is working, the status bar also shows how long it has been working (`⏳ zrb is working (1m 12s)`) and, while a tool call runs, that tool and its elapsed time (`🧰 Shell 8s`). `ZRB_LLM_UI_SHOW_RUNTIME_TIMERS=off` hides both.

### Approval Policies

By default, Zrb prompts for confirmation before executing most tools. This is controlled by YOLO mode and the [Permission Policy](./permission-policy.md) system:

| Mode | Behavior |
|------|----------|
| **YOLO off** | Tools require confirmation unless a tool policy auto-approves them (the built-in chat auto-approves, e.g., `Read`/`LS`/`Glob`/`Grep` inside the current directory, `WebSearch`/`WebFetch`, and safe shell commands) |
| **YOLO on** | All tools auto-approved |
| **Selective YOLO** | Only specified tools auto-approved (e.g., `/yolo Write,Edit`) |
| **Permission Policy** | Fine-grained `ALLOW`/`DENY`/`ASK` rules that can override YOLO |
| **Plan Mode** | Strict read-only mode for discovery. See [Plan Mode](./plan-mode.md) |

**Safe Command Policy:** The `Shell` tool automatically approves known-safe read-only commands (e.g., `ls`, `git status`, `cat`, `grep`) without requiring YOLO mode. Commands with dangerous shell metacharacters (`>`, `|`, `;`, `&`, `` ` ``, `$()`, `\n`, `\r`) always require explicit approval. Known-safe prefixes include `ls`, `cat`, `grep`, `git status`, `printenv`, and similar read-only commands — note that bare `env` is intentionally excluded as `env FOO=1 rm -rf x` can execute arbitrary commands.

### Troubleshooting: Voice & Photo

How `/photo`, `/voice`, `/handsfree` and `/speech` work, and how to configure them, is in [Voice and Camera](voice-camera.md). They depend on OS-level microphone/camera access, so failures are usually platform setup, not a zrb bug. Symptom-by-symptom fixes (macOS/Linux/Windows/WSL/Termux, including building a WSL2 kernel with camera support) are in [Voice & Photo Troubleshooting](voice-photo-troubleshooting.md).

---

## Programmatic Usage (`LLMTask` and `LLMChatTask`)

You can also integrate the LLM directly into your automated workflows using two specialized task types. Both accept `message`, `system_prompt`, and `prompt_manager` as values, templates, callables, or sections — see the full guide at **[Programming the Prompt](programming-the-prompt.md)** for examples of each rung.

### `LLMTask` (Single-Shot)

Use `LLMTask` for single-shot requests where you need the LLM to process input and return a result. Each run is one turn; give it a fixed `conversation_name` and later runs continue that conversation.

```python
from zrb import LLMTask, StrInput, Tpl, cli

summarize_task = cli.add_task(
    LLMTask(
        name="summarize",
        system_prompt="You are an expert summarizer.",
        input=StrInput(name="text"),
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
        input=[StrInput(name="user_message", description="Your message")],
        message=Tpl("{ctx.input.user_message}")
    )
)
```

> 📖 **API Reference:** For the full `LLMChatTask` builder API — tools, guidance, hooks, policies, triggers, and custom commands — see the [LLMChatTask API Reference](../task-types/llmchat-task.md).

### Comparison

`LLMTask` is single-shot (one turn per run, history kept under its `conversation_name`) with no TUI; `LLMChatTask` is an interactive chat with a persistent session. Both take custom tools. Full feature matrix: [LLMChatTask API Reference → Comparison with LLMTask](../task-types/llmchat-task.md#comparison-with-llmtask).

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

🔖 [Documentation Home](../README.md) > [LLM](./) > LLM Integration
