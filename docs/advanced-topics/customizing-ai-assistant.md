🔖 [Home](../../README.md) > [Documentation](../README.md) > [Advanced Topics](./README.md)

# Customizing the AI Assistant (Pollux)

Zrb's AI Assistant (named Pollux by default) is highly extensible. While the default `zrb llm chat` comes with a sensible set of tools and prompts, you can create your own specialized assistants by instantiating `LLMChatTask` and configuring its core components.

This guide explores how to customize the assistant's personality, capabilities, and safety rules.

## 1. Personality and UI

You can change how the assistant presents itself in the TUI using `ui_*` attributes.

```python
from zrb import LLMChatTask, cli

my_assistant = LLMChatTask(
    name="jarvis",
    description="Your personal assistant",
    ui_assistant_name="JARVIS",
    ui_jargon="Just A Rather Very Intelligent System",
    ui_ascii_art="none" # Or provide a custom ASCII string
)
cli.add_task(my_assistant)
```

## 2. Prompt Management

The `PromptManager` allows you to build the system prompt using middlewares. This is more flexible than a single static string.

```python
from zrb.llm.prompt.manager import PromptManager, new_prompt
from zrb.llm.prompt import get_persona_prompt, get_mandate_prompt

chat_task = LLMChatTask(
    name="expert",
    prompt_manager=PromptManager()
)

# Add standard prompts
chat_task.prompt_manager.add_prompt(
    new_prompt(lambda: get_persona_prompt("Expert Bot")),
    new_prompt(lambda: get_mandate_prompt())
)

# Add custom domain-specific instructions
chat_task.prompt_manager.add_prompt(
    new_prompt("You are an expert in Kubernetes and Cloud Native architectures.")
)
```

## 3. Adding Tools

You can equip your assistant with custom Python functions.

```python
def check_db_health() -> str:
    """Checks the health of the production database."""
    return "Database is healthy (0ms latency)"

chat_task.add_tool(check_db_health)
```

## 4. Tool Policies (Auto-Approval)

To improve efficiency, you can define policies to automatically approve certain tool calls based on their arguments.

```python
from zrb.llm.tool_call import auto_approve

# Automatically approve read-only operations on specific directories
chat_task.add_tool_policy(
    auto_approve("read_file", kwargs_patterns={"path": r"^src/.*\.py$"})
)
```

## 5. Custom Response Handlers

Response handlers intercept the user's response to a tool confirmation prompt (the "Allow tool execution?" part). This is how Zrb implements interactive diff editing.

```python
async def my_custom_handler(ui, call, response, next_handler):
    if response.lower() == "log":
        ui.append_to_output("\n📝 Logging this request for audit...")
        return await next_handler(ui, call, "y") # Approve after logging
    return await next_handler(ui, call, response)

chat_task.add_response_handler(my_custom_handler)
```

## 6. Argument Formatters

Argument formatters customize how a tool call is displayed to the user before confirmation.

```python
async def my_formatter(ui, call, args_section):
    if call.tool_name == "run_shell_command":
        return f"       💻 COMMAND: {call.args['command']}\n"
    return None # Fallback to default

chat_task.add_argument_formatter(my_formatter)
```

## 7. History Processors

History processors can modify the conversation history before it's sent to the model. The most common use is automatic summarization.

```python
from zrb.llm.history_processor.summarizer import create_summarizer_history_processor

chat_task.add_history_processor(
    create_summarizer_history_processor(token_threshold=5000)
)
```

By combining these components, you can build powerful, domain-specific AI agents that integrate perfectly with your organization's workflows.

🔖 [Documentation Home](../README.md)