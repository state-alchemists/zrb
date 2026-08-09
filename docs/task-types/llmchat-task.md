🔖 [Documentation Home](../../README.md) > [Task Types](./) > LLMChatTask API

# LLMChatTask API Reference

`LLMChatTask` is Zrb's interactive conversational AI task. Unlike `LLMTask` (single-shot), `LLMChatTask` maintains persistent conversation history, supports a full TUI, and provides a rich post-construction builder API for adding tools, hooks, and custom commands.

---

## Table of Contents

- [Constructor Parameters](#constructor-parameters)
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
    # Input & env
    input: list[AnyInput] | AnyInput | None = None,
    env: list[AnyEnv] | AnyEnv | None = None,
    # Conversation
    message: StrAttr | None = None,
    render_message: bool = True,
    system_prompt: str | None = None,
    render_system_prompt: bool = False,
    prompt_manager: PromptManager | None = None,
    active_skills: StrListAttr | None = None,
    render_active_skills: bool = True,
    # Model
    model: Model | str | None = None,
    render_model: bool = True,
    model_settings: ModelSettings | None = None,
    llm_config: LLMConfig | None = None,
    llm_limiter: LLMLimiter | None = None,
    custom_model_names: StrListAttr | None = None,
    # Conversation management
    conversation_name: StrAttr | None = None,
    render_conversation_name: bool = True,
    history_manager: AnyHistoryManager | None = None,
    ui_greeting: str | None = None,
    # Tools
    tools: list[Tool] | None = None,
    toolsets: list[AbstractToolset] | None = None,
    tool_factories: list[Callable] | None = None,
    toolset_factories: list[Callable] | None = None,
    # Tool confirmation & approval
    tool_confirmation: AnyToolConfirmation = None,
    yolo: BoolAttr = False,
    approval_channel: ApprovalChannel | None = None,
    permissions: PermissionPolicyInput = None,
    sandbox: SandboxInput = None,
    # UI
    ui: UIProtocol | None = None,
    ui_factory: Callable | None = None,
    # Slash-command alias overrides, e.g. UICommands(exit="/quit")
    ui_commands: UICommands | None = None,
    # Flow control (inherited from BaseTask)
    execute_condition: bool | str | Callable = True,
    retries: int = 0,
    retry_period: float = 0,
    upstream: list[AnyTask] | AnyTask | None = None,
    fallback: list[AnyTask] | AnyTask | None = None,
    successor: list[AnyTask] | AnyTask | None = None,
)
```

> This list is not exhaustive. See the `LLMChatTask`/`LLMTask` source or `--help` for the full constructor parameter list, including `cli_only`, `attachment`, `history_processors`, `capabilities`, `custom_commands`, `enable_rewind`/`snapshot_dir`, and more.

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

See **[Programming the Prompt](../advanced-topics/programming-the-prompt.md)** for the full string → template → callable → `PromptManager` ladder.

---

## Builder API (Post-Construction)

After construction, `LLMChatTask` provides a fluent builder API for incremental configuration. All methods are available on the task instance.

### UI Configuration

```python
chat.set_ui(my_ui)
chat.append_ui(another_ui)
chat.set_ui_factory(lambda: MyUI())
chat.append_ui_factory(lambda: OtherUI())
```

### Tools & Toolsets

```python
chat.append_tool(my_tool)
chat.append_tool(my_tool)
chat.append_tool_factory(lambda ctx: create_tool())
chat.append_toolset(my_toolset)
chat.append_toolset_factory(lambda ctx: create_toolset())
```

### Telling the LLM how to use a tool

A tool describes itself through its docstring — pydantic-ai serializes it with
the schema on every request (ADR-0045).

```python
def my_tool(item_id: str) -> dict:
    """Look up one item by id.

    Call ListItems first if you do not have an id; this fails on an unknown one.
    """
    ...

chat.append_tool(my_tool)
```

For cross-cutting policy, register a prompt section and place its name in
`ZRB_LLM_INCLUDE_SECTIONS`:

```python
chat.prompt_manager.register_section(
    "tool_policy", lambda ctx: "## My rules\n- Always validate before writing."
)
```

### History Processors

```python
chat.append_history_processor(my_processor)
chat.append_history_processor(my_processor)
```

### Hook Factories

```python
chat.append_hook_factory(lambda hm: hm.register(my_hook, events=[HookEvent.SESSION_START]))
chat.append_hook_factory(lambda hm: hm.register(other_hook, events=[HookEvent.SESSION_END]))
```

### Approval & Policy

```python
chat.set_approval_channel(channel)
chat.append_approval_channel(channel)
chat.prepend_tool_policy(policy)
chat.prepend_response_handler(handler)
chat.prepend_argument_formatter(formatter)
chat.permissions = my_permission_policy  # read/write property; also a constructor arg
chat.sandbox = my_sandbox_policy         # read/write property; also a constructor arg
```

See [Permission Policy](../advanced-topics/permission-policy.md) and
[Sandbox](../advanced-topics/sandbox.md) for the accepted policy shapes.

### Triggers & Custom Commands

```python
chat.append_trigger(my_async_iterator)
chat.append_trigger(my_async_iterator)
chat.append_custom_command(my_command)
chat.append_custom_command(my_command)
```

### History Manager

```python
chat.set_history_manager(FileHistoryManager(history_dir="./my-history/"))
```

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
| **Hook system** | Full lifecycle hooks | Same |
| **History processors** | `append_history_processor` | Same |
| **System prompt** | Via `system_prompt` or `prompt_manager` | Same |

---

> **Tip:** Use `LLMTask` for automated pipelines where you need the LLM as a processing step. Use `LLMChatTask` when you want an interactive assistant that users can converse with.

🔖 [Documentation Home](../../README.md) > [Task Types](./) > LLMChatTask API
