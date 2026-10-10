🔖 [Documentation Home](../README.md) > LLM

# The Agent: `zrb llm chat` and the LLM Tasks

Everything about zrb's coding agent: using it, configuring it, and programming it from Python. New here? Do [Installation → First LLM Chat](../installation/installation.md#first-llm-chat) first, then read the first two pages below.

## Using the chat

| Page | Read it to… |
|---|---|
| [LLM Integration](llm-integration.md) | Learn the chat TUI: slash commands, attachments, sessions, `/rewind`, and the `LLMTask`/`LLMChatTask` types |
| [Choosing Between Agent Harnesses](harness-comparison.md) | Decide when zrb is the right tool, compared with Claude Code, opencode and others |
| [Plan Mode](plan-mode.md) | Let the agent investigate and plan read-only before it edits |
| [Permission Policy](permission-policy.md) | Decide which tool calls run, ask, or are denied |
| [Sandbox](sandbox.md) | Confine the agent's file access and shell commands |
| [Voice and Camera](voice-camera.md) | Use `/photo`, dictation, and replies read aloud |
| [Voice & Photo Troubleshooting](voice-photo-troubleshooting.md) | Fix microphone, speaker and camera setup per platform |

## Configuring

| Page | Read it to… |
|---|---|
| [LLM Configuration](../configuration/llm-config.md) | Pick a provider and model, and look up any `ZRB_LLM_*` variable |
| [LLM Component Collections](../configuration/llm-collections.md) | Add or filter skills, agents, hooks, prompts and tools from `zrb_init.py` |
| [Claude Code Compatibility](claude-compatibility.md) | Reuse `CLAUDE.md`, skills, agents, hooks and plugins — and see where zrb differs |
| [Hooks](hooks.md) | Run commands, prompts or agents at lifecycle events |
| [MCP Support](mcp-support.md) | Connect Model Context Protocol servers |
| [LSP Support](lsp-support.md) | Give the agent language-server code intelligence |

## Programming the agent in Python

| Page | Read it to… |
|---|---|
| [Programming the Agent](programming-the-agent.md) | See every way to shape the agent from Python, in one overview |
| [Programming the Prompt](programming-the-prompt.md) | Go from a plain `message` string to a composed `PromptManager` |
| [Extending the LLM](extending-the-llm.md) | Add tools and sub-agents, and tune model capabilities and context |
| [LLMChatTask API Reference](../task-types/llmchat-task.md) | Look up `LLMChatTask`'s constructor and builder methods |
| [LLMTask API Reference](../task-types/llm-task.md) | Look up `LLMTask`'s parameters, and the methods a subclass can override |
| [Programming the Voice](programming-the-voice.md) | Script voice input and output, or plug in your own speech backend |
| [Customizing Tool Approval](tool-approval.md) | Change what the approval prompt shows, auto-approve or deny calls in code, and add your own answers |
| [Custom UI and Approval Channels](llm-custom-ui.md) | Put the agent behind Telegram, Discord, HTTP or your own UI |

## For contributors

| Page | Read it to… |
|---|---|
| [LLM Chat Request Lifecycle](llm-chat-lifecycle.md) | Follow one `zrb llm chat` request through the source code |
| [LLM Journal System](../technical-specs/llm-context.md) | See how the journal is stored and injected |
| [Architecture](../architecture/README.md) | Understand the design of each LLM subsystem |

---

🔖 [Documentation Home](../README.md) > LLM
