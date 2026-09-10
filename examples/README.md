🔖 [Documentation Home](../README.md)

# Examples

Each folder is a self-contained `zrb_init.py` you can copy into your own project and adapt. Start with **Basics** if you're new to Zrb, then jump to whichever topic matches what you're building.

## Basics

| Example | What it demonstrates |
|---|---|
| [`basic-task`](basic-task) | `Task` with inputs and a plain Python action |
| [`cmd-task`](cmd-task) | `CmdTask` — running shell commands |
| [`task-dependencies`](task-dependencies) | Chaining tasks with `>>` |
| [`task-groups`](task-groups) | Organizing tasks into subcommands with `Group` |
| [`async-task`](async-task) | Writing an async task with `asyncio` |

## Automation

| Example | What it demonstrates |
|---|---|
| [`trigger-scheduler`](trigger-scheduler) | Event-driven and scheduled (cron) tasks |
| [`web-auth`](web-auth) | Configuring authentication for the web UI |

## Programming the LLM Agent

| Example | What it demonstrates |
|---|---|
| [`agent-in-pipeline`](agent-in-pipeline) | An `LLMTask` as an ordinary DAG node, with a custom in-process tool |
| [`llm-hooks`](llm-hooks) | Lifecycle hooks (`PRE_TOOL_USE`, etc.) for an `LLMChatTask` |
| [`permission-policy`](permission-policy) | Custom `PermissionPolicy` to gate tool use |
| [`plan-mode`](plan-mode) | Plan Mode's read-only discovery phase |
| [`model-tiering`](model-tiering) | Automatic model downgrading via `model_getter`/`model_renderer` |
| [`live-context`](live-context) | Injecting live, per-turn runtime state into the prompt |
| [`lsp-config`](lsp-config) | Registering a custom Language Server for code intelligence |

## Custom Chat UIs

| Example | What it demonstrates |
|---|---|
| [`chat-minimal-ui`](chat-minimal-ui) | The simplest possible custom UI backend |
| [`chat-sse`](chat-sse) | Server-Sent Events + CLI dual mode |
| [`chat-telegram`](chat-telegram) | CLI + Telegram dual mode |

## Appearance

| Example | What it demonstrates |
|---|---|
| [`themes`](themes) | Shell scripts for curated `zrb llm chat` color palettes |

---

Looking for the API reference behind any of these? See the [Documentation Directory](../README.md#️-documentation-directory) in the main README.
