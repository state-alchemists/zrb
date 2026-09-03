🔖 [Documentation Home](../../README.md) > [Task Types](./) > LLMChatTask API

# LLMChatTask API Reference

`LLMChatTask` is Zrb's interactive conversational AI task. Unlike `LLMTask` (single-shot), `LLMChatTask` maintains persistent conversation history, supports a full TUI, and provides a rich post-construction builder API for adding tools, hooks, and custom commands.

---

## Table of Contents

- [Constructor Parameters](#constructor-parameters)
- [Model, Model Settings & Capabilities](#model-model-settings--capabilities)
- [Seeding the Conversation](#seeding-the-conversation)
- [Builder API (Post-Construction)](#builder-api-post-construction)
- [Comparison with LLMTask](#comparison-with-llmtask)

---

## Constructor Parameters

```python
from zrb import LLMChatTask

chat = LLMChatTask(
    name: str = ...,
    # Appearance
    color: int | None = None,
    icon: str | None = None,
    description: str | None = None,
    cli_only: bool = False,
    # Input & env
    input: list[AnyInput] | AnyInput | None = None,
    env: list[AnyEnv] | AnyEnv | None = None,
    # Conversation
    message: StrAttr | None = None,
    render_message: bool = True,
    attachment: UserContent | list[UserContent] | Callable | None = None,
    system_prompt: Callable[[AnyContext], str | fstring | None] | str | None = None,
    render_system_prompt: bool = False,
    prompt_manager: PromptManager | None = None,
    active_skills: StrListAttr | None = None,
    render_active_skills: bool = True,
    # Model — see Model, Model Settings & Capabilities, below
    model: Callable[[AnyContext], Model | str | fstring | None] | Model | None = None,
    render_model: bool = True,
    model_settings: ModelSettings | Callable[[AnyContext], ModelSettings] | None = None,
    capabilities: list[AbstractCapability] | None = None,
    llm_limiter: LLMLimiter | None = None,
    model_getter: Callable | None = None,
    model_renderer: Callable | None = None,
    custom_model_names: StrListAttr | None = None,
    # Conversation management
    conversation_name: StrAttr | None = None,
    render_conversation_name: bool = True,
    history_manager: AnyHistoryManager | None = None,
    history_processors: list[HistoryProcessor] | None = None,
    # Tools
    tools: list[Tool | ToolFuncEither] | None = None,
    toolsets: list[AbstractToolset] | None = None,
    tool_factories: list[Callable] | None = None,
    toolset_factories: list[Callable] | None = None,
    # Tool confirmation & approval
    tool_confirmation: AnyToolConfirmation = None,
    yolo: BoolAttr = False,
    approval_channel: AnyApprovalChannel | None = None,
    permissions: PermissionPolicyInput = None,
    sandbox: SandboxInput | BoolAttr = None,
    tool_policies: list[ToolPolicy] | None = None,
    response_handlers: list[ResponseHandler] | None = None,
    argument_formatters: list[ArgumentFormatter] | None = None,
    # Hooks — see Hook System, below
    hook_manager: HookManager | None = None,
    # UI & identity
    ui: AnyUI | None = None,
    ui_factory: Callable | None = None,
    include_default_ui: bool = True,
    interactive: BoolAttr = True,
    markdown_theme: Theme | None = None,
    ui_greeting: StrAttr | None = None,
    ui_assistant_name: StrAttr | None = None,
    ui_jargon: StrAttr | None = None,
    ui_ascii_art: StrAttr | None = None,
    # each ui_* text field above has a matching render_ui_* flag (default True)
    # Slash-command aliases, yolo_xcom_key, show_*_models — see UIConfig, below
    ui_config: UIConfig | None = None,
    # Extra commands & external drivers — see Custom UI Guide
    custom_commands: list[AnyCustomCommand] | None = None,
    triggers: list[Callable] | None = None,
    # Rewind (see Rewind & Snapshots in the LLM Configuration guide)
    enable_rewind: bool | None = None,
    snapshot_dir: StrAttr | None = None,
    # Flow control (inherited from BaseTask)
    execute_condition: bool | str | Callable = True,
    retries: int = 0,
    retry_period: float = 0,
    upstream: list[AnyTask] | AnyTask | None = None,
    fallback: list[AnyTask] | AnyTask | None = None,
    successor: list[AnyTask] | AnyTask | None = None,
)
```

> This list is not exhaustive. See the `LLMChatTask`/`LLMTask` source or `--help` for the full constructor parameter list, including readiness-check tuning and the other `BaseTask` flow-control parameters inherited unchanged.

---

## Model, Model Settings & Capabilities

`model`, `model_settings`, and `capabilities` are pydantic-ai's own types, passed straight through unchanged (ADR-0036) — zrb doesn't wrap or reinterpret them. For what `Model`/`ModelSettings` accept per provider, and the full catalogue of capability classes, see [pydantic-ai's documentation](https://ai.pydantic.dev).

- **`model`** — a model name string (`"openai:gpt-4o"`) or a pydantic-ai `Model` instance. See [LLM & Rate Limiter Configuration](../configuration/llm-config.md) for the supported-provider list, credentials, and the task's own `model_getter`/`model_renderer` hooks for tiering or A/B routing.
- **`model_settings`** — a pydantic-ai `ModelSettings` (temperature, `openai_reasoning_effort`, …), or a callable taking the context for per-run values. See [Core LLM Routing](../configuration/llm-config.md#1-core-llm-routing) for the defaults zrb layers on top (`ZRB_LLM_THINKING`, `openai_reasoning_summary`, …).
- **`capabilities`** — a list of pydantic-ai `AbstractCapability` instances (`ProcessHistory`, `Thinking`, `WebSearch`, `PrepareTools`, …), pydantic-ai's own agent-extension mechanism. It replaced the `Agent(history_processors=...)` constructor kwarg pydantic-ai itself carried before 2.36 (see [ADR-0041](../adr/adr-0041.md)). Do not confuse it with either of these zrb-specific things that share part of the name:
  - `history_processors` (below) — zrb's **own** history-rewriting pipeline (`append_history_processor`), which predates and is independent of pydantic-ai's `capabilities`/`ProcessHistory`.
  - the [Model Capabilities registry](../llm/extending-the-llm.md#model-capabilities) — zrb's per-model table of modality/parallel-tool-call support, unrelated to this constructor argument.

`custom_model_names`, and `ui_config`'s `show_ollama_models`/`show_pydantic_ai_models` fields, only affect the `/model` picker's autocomplete list in the chat TUI — see [Model Autocomplete](../configuration/llm-config.md#8-model-autocomplete).

`active_skills`/`render_active_skills` pre-activate named skills for the session (skipping their normal on-demand discovery), rendered as templates by default; see the skill catalogue notes under [System Prompts & Identity](../configuration/llm-config.md#4-system-prompts--identity).

---

## Seeding the Conversation

Both `message` and `system_prompt` are rendered attributes, so you can hand the chat data produced by an upstream task before the user ever types. The rule of thumb:

- **`message`** — the *opening user turn*. Set it to send a first prompt automatically; leave it empty to drop the user straight into the TUI.
- **`system_prompt`** — *standing background* the user then converses against. This is where you put an upstream command's output when the whole point is to let the user ask questions about it.

```python
from zrb import cli, CmdTask, LLMChatTask

status = cli.add_task(CmdTask(name="git-status", cmd="git status && git log --oneline -20"))

chat = cli.add_task(
    LLMChatTask(
        name="ask-repo",
        upstream=[status],
        system_prompt=lambda ctx: (
            "You are a git assistant. Here is the current repository state; "
            "answer the user's questions about it.\n\n"
            f"{ctx.xcom['git-status'].pop()}"
        ),
        ui_greeting="Ask me anything about the current repo state.",
        # No `message` → the TUI opens and waits for the user.
    )
)

status >> chat
```

> **Note:** `system_prompt` is **not** rendered by default (`render_system_prompt=False`), so `{ ... }` in a system-prompt *string* stays literal. Pass a callable (as above) or set `render_system_prompt=True`. `message` **is** rendered by default.

See **[Programming the Prompt](../llm/programming-the-prompt.md)** for the full string → template → callable → `PromptManager` ladder.

---

## Builder API (Post-Construction)

After construction, `LLMChatTask` provides a fluent builder API for incremental configuration. All methods are available on the task instance.

Every ordered collection below (tools, toolsets, factories, processors, policies,
handlers, formatters, triggers, custom commands, UIs) exposes the full R5 verb
set: `append_X`, `prepend_X`, `set_X`s, `remove_X` — see
[Framework Conventions](../contributing/framework-conventions.md). The
snippets below show one or two verbs per collection for brevity, not the
complete set.

### Component Slots

Every component a task may hold exactly one of is a settable property (R8) —
this works even on an already-defined task, such as the built-in `llm_chat`
from `zrb_init.py`:

```python
from zrb.builtin import llm_chat
from zrb.llm.prompt.manager import PromptManager

llm_chat.prompt_manager = PromptManager(prompts=["Just this one bot."])
llm_chat.hook_manager = my_hook_manager      # or None to go back to "fresh per run"
llm_chat.llm_limiter = my_llm_limiter        # or None to remove the limit
llm_chat.markdown_theme = my_rich_theme      # or None for the default
llm_chat.ui_config = UIConfig(exit_commands=["/bye"])
llm_chat.model_getter = my_model_getter      # or None to remove the hook
llm_chat.model_renderer = my_model_renderer  # or None to remove the hook
```

`history_manager`, `sandbox`, and `permissions` are the same kind of slot —
see their own sections below. Assigning the wrong type raises `TypeError`
naming the expected class, at the assignment site.

### UI Configuration

```python
chat.append_ui(my_ui)
chat.prepend_ui(another_ui)
chat.set_uis([my_ui, another_ui])
# Factories are invoked with 8 kwargs (ctx, llm_task, history_manager,
# ui_commands, initial_message, initial_conversation_name, initial_yolo,
# initial_attachments) — accept **kwargs, or use create_ui_factory to wire them.
chat.ui_factories = [lambda **kw: MyUI(**kw)]   # settable property
chat.append_ui_factory(lambda **kw: OtherUI(**kw))
```

### Tools & Toolsets

```python
chat.append_tool(my_tool)
chat.append_tool_factory(lambda ctx: create_tool())
chat.append_toolset(my_toolset)
chat.append_toolset_factory(lambda ctx: create_toolset())
```

### Telling the LLM how to use a tool

A tool describes itself through its docstring — pydantic-ai serializes it with the schema on every request (ADR-0045).

```python
def my_tool(item_id: str) -> dict:
    """Look up one item by id.

    Call ListItems first if you do not have an id; this fails on an unknown one.
    """
    ...

chat.append_tool(my_tool)
```

For cross-cutting policy, append it to the system prompt (emitted after the built-in sections):

```python
chat.prompt_manager.append_prompt(
    "## My rules\n- Always validate before writing."
)
```

### History Processors

```python
chat.append_history_processor(my_processor)
```

### Hook Factories

```python
chat.append_hook_factory(lambda hm: hm.add_hook(my_hook, events=[HookEvent.SESSION_START]))
chat.append_hook_factory(lambda hm: hm.add_hook(other_hook, events=[HookEvent.SESSION_END]))
```

> **Isolation differs from `LLMTask`.** `LLMChatTask` builds a **fresh** `HookManager` per execution and replays every registered factory onto it each time, so one session's hooks never leak into the next. `LLMTask` instead holds a **persistent** manager — on `LLMTask`, the *first* `append_hook_factory` call swaps the process-wide default for a fresh task-local manager (later calls apply to that same manager), unless a manager was passed explicitly to the constructor, which is never swapped. See [ADR-0072](../adr/adr-0072.md) and [Hooks — Defining Hooks Programmatically](../llm/hooks.md#defining-hooks-programmatically-python) for the full rationale.

### Approval & Policy

```python
chat.approval_channels = [channel]   # settable property
chat.append_approval_channel(channel)
chat.prepend_tool_policy(policy)
chat.prepend_response_handler(handler)
chat.prepend_argument_formatter(formatter)
chat.permissions = my_permission_policy  # read/write property; also a constructor arg
chat.sandbox = my_sandbox_policy         # read/write property; also a constructor arg
```

See [Permission Policy](../llm/permission-policy.md) and [Sandbox](../llm/sandbox.md) for the accepted policy shapes.

### Triggers & Custom Commands

```python
chat.append_trigger(my_async_iterator)
chat.append_custom_command(my_command)
```

### History Manager

```python
chat.history_manager = FileHistoryManager(history_dir="./my-history/")
```

`history_manager`, `conversation_name`/`render_conversation_name` are also readable as one group via the `history_config` read-only property (a `HistoryConfig`, computed fresh on every read — never cached, so a `history_manager` reassignment is immediately visible through it):

```python
chat.history_config.history_manager
chat.history_config.conversation_name
```

Same property, same fields, on both `LLMTask` and `LLMChatTask` (ADR-0072).

---

## Comparison with LLMTask

| Feature | `LLMChatTask` | `LLMTask` |
|---------|---------------|-----------|
| **Use case** | Interactive conversation | Single-shot processing |
| **Conversation history** | Persistent across turns | None (one request) |
| **TUI** | Full-screen terminal UI | No TUI (programmatic only) |
| **Custom commands** | Yes | No |
| **Triggers (async iterables)** | Yes | No |
| **Response handlers** | Yes | No |
| **Tool policies** | Yes | No |
| **Permission policy** | `permissions=` (arg + property) | Same |
| **Filesystem sandbox** | `sandbox=` (arg + property) | Same |
| **Shared tool APIs** | `append_tool`, `append_tool_factory`, `append_toolset` | Same |
| **Hook system** | `append_hook_factory` onto a **fresh** manager per run | `append_hook_factory` onto a **persistent** manager ([ADR-0072](../adr/adr-0072.md)) |
| **History processors** | `append_history_processor` | Same |
| **System prompt** | Via `system_prompt` or `prompt_manager` | Same |

---

> **Tip:** Use `LLMTask` for automated pipelines where you need the LLM as a processing step. Use `LLMChatTask` when you want an interactive assistant that users can converse with.

🔖 [Documentation Home](../../README.md) > [Task Types](./) > LLMChatTask API
