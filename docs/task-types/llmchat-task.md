🔖 [Documentation Home](../../README.md) > [Task Types](./) > LLMChatTask API

# LLMChatTask API Reference

`LLMChatTask` is Zrb's interactive conversational AI task. Unlike `LLMTask` (single-shot), `LLMChatTask` maintains persistent conversation history, supports a full TUI, and provides a rich post-construction builder API for adding tools, hooks, and custom commands.

---

## Table of Contents

- [Constructor Parameters](#constructor-parameters)
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
    # Summarization
    ui_summarize_commands: list[str] | None = None,
    # Flow control (inherited from BaseTask)
    execute_condition: bool | str | Callable = True,
    retries: int = 0,
    retry_period: float = 0,
    upstream: list[AnyTask] | AnyTask | None = None,
    fallback: list[AnyTask] | AnyTask | None = None,
    successor: list[AnyTask] | AnyTask | None = None,
)
```

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
chat.add_tool(my_tool)
chat.append_tool(my_tool)
chat.add_tool_factory(lambda ctx: create_tool())
chat.add_toolset(my_toolset)
chat.add_toolset_factory(lambda ctx: create_toolset())
```

### Tool Guidance

```python
from zrb import ToolGuidance

chat.add_tool_guidance(
    ToolGuidance(
        group_name="My Tools",
        tool_name="MyTool",
        when_to_use="When user asks about X",
        key_rule="Always call Validate first",
    )
)

# For dynamic tool names (resolved at runtime):
chat.add_tool_guidance_factory(
    lambda ctx: ToolGuidance(
        group_name="Zrb Tasks",
        tool_name=f"List{CFG.ROOT_GROUP_NAME.capitalize()}Tasks",
        when_to_use="Before running any task",
    )
)
```

> **Note:** `add_tool_guidance_factory` is available on both `LLMChatTask` and `LLMTask`.

### History Processors

```python
chat.add_history_processor(my_processor)
chat.append_history_processor(my_processor)
```

### Hook Factories

```python
chat.add_hook_factory(lambda hm: hm.register(my_hook, events=[HookEvent.SESSION_START]))
chat.append_hook_factory(lambda hm: hm.register(other_hook, events=[HookEvent.SESSION_END]))
```

### Approval & Policy

```python
chat.set_approval_channel(channel)
chat.append_approval_channel(channel)
chat.add_tool_policy(policy)
chat.add_response_handler(handler)
chat.add_argument_formatter(formatter)
chat.permissions = my_permission_policy  # read/write property; also a constructor arg
chat.sandbox = my_sandbox_policy         # read/write property; also a constructor arg
```

See [Permission Policy](../advanced-topics/permission-policy.md) and
[Sandbox](../advanced-topics/sandbox.md) for the accepted policy shapes.

### Triggers & Custom Commands

```python
chat.add_trigger(my_async_iterator)
chat.append_trigger(my_async_iterator)
chat.add_custom_command(my_command)
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
| **`add_tool_guidance_factory`** | Yes | Yes |
| **Custom commands** | Yes | No |
| **Triggers (async iterables)** | Yes | No |
| **Response handlers** | Yes | No |
| **Tool policies** | Yes | No |
| **Permission policy** | `permissions=` (arg + property) | Same |
| **Filesystem sandbox** | `sandbox=` (arg + property) | Same |
| **Shared tool APIs** | `add_tool`, `add_toolset`, `add_tool_guidance` | Same |
| **Hook system** | Full lifecycle hooks | Same |
| **History processors** | `add_history_processor` | Same (via constructor) |
| **System prompt** | Via `system_prompt` or `prompt_manager` | Same |

---

> **Tip:** Use `LLMTask` for automated pipelines where you need the LLM as a processing step. Use `LLMChatTask` when you want an interactive assistant that users can converse with.

🔖 [Documentation Home](../../README.md) > [Task Types](./) > LLMChatTask API
