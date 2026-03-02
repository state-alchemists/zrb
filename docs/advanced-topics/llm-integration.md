🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > LLM Integration

# LLM Integration (AI Assistant)

Zrb comes with a powerful, built-in AI assistant that can understand your codebase, perform actions on your behalf, and automate complex software engineering tasks.

## Interactive Chat (`zrb llm chat`)

The primary way to interact with AI Assistang is through an interactive terminal user interface (TUI).

```bash
zrb llm chat "Can you help me refactor the user authentication service?"
```

This launches a full-screen chat application where you can have a conversation with the assistant.

### Key TUI Commands

Within the TUI, you can use several slash (`/`) and bang (`!`) commands to control the session:

*   `/q`, `/bye`, `/quit`, `/exit`: Exit the application.
*   `/info`, `/help`: Show the help message with all available commands.
*   `/compress`, `/compact`: Summarize the current conversation history to free up context window space.
*   `/model <name>`: Switch the LLM model for the current session (e.g., `/model openai:gpt-4o`).
*   `/yolo`: Toggles "YOLO mode." When enabled, the assistant will execute all tool calls (like file edits or shell commands) without asking for your permission. Use with caution!
*   `/load <name>`: Switches the current conversation to a named session. If the session doesn't exist, a new empty session history will be created implicitly.
*   `/save <name>`: Saves the current conversation history to a new named session.
*   `/attach <file_path>`: Attaches a file to your next message.
*   `>` or `/redirect <file_path>`: Saves the assistant's last response to the specified file.
*   `!` or `/exec <shell_command>`: Executes a shell command directly from the TUI. The output will be streamed into the chat window.

Any other `/command` that matches a loaded skill will be executed as a skill.

## Programmatic Usage (`LLMTask` and `LLMChatTask`)

You can also integrate the LLM directly into your automated workflows using two specialized task types.

### `LLMTask` (Single-Shot)
Use `LLMTask` for single-shot requests where you need the LLM to process some input and return a result without a conversational history.

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

## Custom Tools and Sub-agents

You can extend the assistant's capabilities with your own Python functions.

### Custom Python Tools
Any Python function can be registered as a tool. Just add it to an `LLMChatTask`. The assistant will automatically understand the function's purpose from its docstring and arguments.

```python
def get_weather(location: str) -> str:
    """Gets the current weather for a given location."""
    # ... your implementation ...

my_chat_task.add_tool(get_weather)
```

### Sub-agents
Zrb can automatically discover and manage sub-agents defined in JSON or YAML files within an `agents/` directory. The primary assistant can then delegate complex tasks to these specialized agents using the built-in `delegate_to_agent` tool. This is useful for isolating context and keeping the main conversation history clean.

## Context Management

The AI Assistant is designed for long-running, complex tasks and has a sophisticated context management system.

### Two-Tier Summarization System
To avoid exceeding the context window of the underlying LLM, Zrb uses a two-tier summarization system:
1.  **Message-level Summarization**: If a single tool output (like a large file or a long command output) is too large, it is summarized before being added to the history.
2.  **Conversational Summarization**: As the overall conversation history grows, older parts of the conversation are summarized into a concise XML `<state_snapshot>`. This snapshot preserves key knowledge, user goals, and recent actions, ensuring the assistant doesn't lose track of the mission.

### Journal System
For persistent, long-term memory, Zrb uses a journal system. This is a directory of Markdown files (by default in `~/.zrb/llm-notes/`) where the assistant can keep notes. The `index.md` file from this directory is automatically included in the assistant's context on every turn.
