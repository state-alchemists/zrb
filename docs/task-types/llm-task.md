🔖 [Documentation Home](../README.md) > [Task Types](./) > LLMTask API

# LLMTask API Reference

`LLMTask` sends one message to a model, lets it call tools, and returns the answer as the task's result. It has no TUI and no slash commands, so it fits a pipeline step. For an interactive conversation use [`LLMChatTask`](llmchat-task.md).

```python
from zrb import LLMTask, StrInput, Tpl, cli

summarize = cli.add_task(
    LLMTask(
        name="summarize",
        input=StrInput(name="path"),
        message=Tpl("Summarize {ctx.input.path} in three bullets."),
        tools=[read_file],
        yolo=True,
    )
)
```

---

## Table of Contents

- [Constructor Parameters](#constructor-parameters)
- [The system prompt starts empty](#the-system-prompt-starts-empty)
- [Tool approval in an unattended task](#tool-approval-in-an-unattended-task)
- [Properties and builder methods](#properties-and-builder-methods)
- [Methods a subclass can override](#methods-a-subclass-can-override)

---

## Constructor Parameters

Every `BaseTask` keyword (`input`, `env`, `upstream`, `retries`, ...) is accepted too. `retry_if` defaults to "retry unless the error is permanent".

| Parameter | Default | What it does |
|---|---|---|
| `message` | `None` | The user message. A `Tpl` or callable is resolved against the context |
| `attachment` | `None` | Images or files sent with the message: one item, a list, or a callable |
| `system_prompt` | `None` | The system prompt. Used only when `prompt_manager` is not given |
| `prompt_manager` | `None` | A `PromptManager` composing the system prompt. See below |
| `active_skills` | `None` | Skills to pre-activate |
| `model` / `model_settings` | `CFG.LLM_MODEL` / config | Model name or pydantic-ai `Model`, and its settings; both may be callables |
| `model_getter` / `model_renderer` | `None` | Transform the resolved model, before and after; see [LLMChatTask → Model](llmchat-task.md#model-model-settings--capabilities) |
| `custom_model_names` | `None` | Extra names for the model picker |
| `capabilities` | `None` | pydantic-ai capabilities for the run |
| `llm_limiter` | shared `llm_limiter` | Rate and token limiter. `None` means the shared default, not "unlimited" |
| `tools` / `toolsets` | `[]` | Tools and toolsets the model may call |
| `tool_factories` / `toolset_factories` | `[]` | Callables building tools per run from the context |
| `history_processors` | `[]` | Callables rewriting history before each request |
| `conversation_name` | random per run | Name the history is stored under. Set it to keep history across runs |
| `history_manager` | file store under `ZRB_LLM_HISTORY_DIR` | Where history is persisted |
| `hook_manager` | process-wide `hook_manager` | Lifecycle hooks; see [Hooks → Scoped to one task](../llm/hooks.md#scoped-to-one-task-append_hook_factory) |
| `tool_confirmation` | `None` | Decides tool calls needing approval: a `ToolCallHandler` or a callable taking the call |
| `approval_channel` | `None` | Sends approval requests to someone who can answer |
| `permissions` | `ZRB_LLM_PERMISSIONS` | [Permission policy](../llm/permission-policy.md) |
| `sandbox` | `None` | [Sandbox](../llm/sandbox.md) policy |
| `yolo` | `False` | Skip approval: `True`, or a comma-separated string or set of tool names |
| `dynamic_yolo` | `None` | Callable deciding `yolo` per tool call. Replaces `yolo` when set |
| `ui` | `None` | UI receiving streamed output and prompts |
| `summarize_commands` | `[]` | Messages that compress history instead of asking the model |

**`dynamic_yolo`** is called per tool call with `(tool_def, args)` when it accepts two positional arguments, otherwise with `(tool_def)` alone. Accept `args` if you use `arg_pattern` [permission rules](../llm/permission-policy.md), since judging those needs the call's arguments. It is also called once with no arguments at the start of each run, so give both parameters defaults:

```python
def allow_reads(tool_def=None, args=None) -> bool:
    return tool_def is not None and tool_def.name in ("Read", "Grep")

LLMTask(name="audit", message="...", dynamic_yolo=allow_reads)
```

**`summarize_commands`**: when the resolved `message` equals one of these strings, the task compresses the stored history (`summarize_history`) and returns `"Conversation history compressed."` without a model turn. Only useful with a fixed `conversation_name`.

## The system prompt starts empty

Without `prompt_manager`, the task builds `PromptManager(prompts=[system_prompt], include_sections=[])`. So its system prompt is exactly `system_prompt`, or empty. None of zrb's built-in sections (persona, workflow rules, skill catalogue, project docs) are sent. To include them, pass `prompt_manager=PromptManager()`.

When you pass `prompt_manager`, `system_prompt` is ignored. Add your text to the manager: `PromptManager(prompts=["..."])` or `task.prompt_manager.append_prompt("...")`. Details: [Programming the Prompt](../llm/programming-the-prompt.md#rung-4--the-system-prompt).

## Tool approval in an unattended task

Each tool call that is not approved by `yolo`, a permission rule or a hook needs someone to answer. An `LLMTask` has no terminal prompt of its own, so give it one of:

- `yolo=True` or `dynamic_yolo=...`, to trust the tools;
- `permissions=...` with `allow` rules for what it may do;
- `tool_confirmation=ToolCallHandler(...)` plus a `ui`, to ask in the terminal (see [Customizing Tool Approval](../llm/tool-approval.md));
- `approval_channel=...`, to ask somewhere else (see [Approval Channels](../llm/llm-custom-ui.md#approval-channels)).

## Properties and builder methods

| Member | What it is for |
|---|---|
| `prompt_manager`, `tools`, `toolsets`, `tool_factories`, `toolset_factories`, `history_processors` | Read or replace the matching constructor value |
| `tool_confirmation`, `approval_channel`, `permissions`, `sandbox`, `hook_manager`, `history_manager`, `custom_model_names`, `model_getter`, `model_renderer` | Read or replace the matching constructor value |
| `llm_limiter` | The limiter in force (the shared one when none was given). Read-only |
| `append_tool`, `append_toolset`, `append_tool_factory`, `append_toolset_factory`, `append_history_processor` | Add after what is registered |
| `append_hook_factory` | Register hooks. The first call swaps the shared manager for a task-local one |
| `set_ui(ui)`, `append_ui(ui)`, `get_uis()`, `uis` | Replace, add to, copy or read the attached UIs. `set_ui(None)` detaches all |
| `append_stream_observer`, `prepend_stream_observer`, `set_stream_observers`, `remove_stream_observer` | Callables seeing every streamed event; see [LLMChatTask → Stream Observers](llmchat-task.md#stream-observers) |
| `history_config` | `history_manager` and `conversation_name` as one `HistoryConfig`, recomputed on each read |
| `get_system_prompt(ctx)`, `get_model(ctx)`, `get_model_settings(ctx)`, `get_all_tools(ctx)`, `get_all_toolsets(ctx)` | What a run would use, resolved against a context |

## Methods a subclass can override

The run calls these on the task, so overriding one in a subclass changes the run.

| Method | Default behavior |
|---|---|
| `post_process_output(output)` | Strips terminal styling from a string result. Override to parse or validate the answer |
| `get_effective_prompt(ctx, user_message, user_attachments, message_history)` | Returns the message and attachments. On a retry whose message is already the last user turn, sends a retry notice instead, so the turn is not duplicated |
| `handle_run_error(ctx, history_manager, conversation_name, error, partial_run=None)` | Saves the failed run's history plus an error note, so a retry sees what happened. A context-length error saves history without the note |
| `save_cancelled_history(history_manager, conversation_name, message_history, user_message, partial_run=None)` | Saves partial history plus a cancellation marker when the run is cancelled |
| `get_history_manager(ctx)` | The configured store, or the default file store |
| `get_conversation_name(ctx)` | The resolved `conversation_name`, or a fresh random name |

`is_context_length_error(error)` decides whether a failure was the model rejecting an over-long prompt. Override it to recognize a provider's own wording; `handle_run_error` then saves the history unchanged for that error instead of growing it.

```python
import json

class JsonTask(LLMTask):
    def post_process_output(self, output):
        return json.loads(super().post_process_output(output))
```

---

🔖 [Documentation Home](../README.md) > [Task Types](./) > LLMTask API
