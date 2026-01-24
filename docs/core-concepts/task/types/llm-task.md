🔖 [Documentation Home](../../../../README.md) > [Core Concepts](../../../README.md) > [Task](../../README.md) > [Task Types](./README.md) > LLMTask

# `LLMTask` and `LLMChatTask`

Zrb provides powerful tools for integrating Large Language Models (LLMs) into your workflows.

- **`LLMTask`**: A base task for one-shot or programmatically managed LLM interactions.
- **`LLMChatTask`**: A specialized task that provides a full-featured, interactive Terminal User Interface (TUI) for chatting with an AI assistant. This is what powers the `zrb llm chat` command.

At their core, these tasks use a stateful, context-aware architecture that manages conversation history, persistent notes, and a wide array of tools.

## Context and History Management

Zrb uses a sophisticated system to manage the context of a conversation, which is divided into three main parts:

1.  **Persistent Notes**: Stored in `~/.zrb/notes.json`, these are location-aware facts that the LLM remembers across sessions. See [LLM Notes & Context](../../../technical-specs/llm-context.md) for details.

2.  **Conversation Summary**: As the conversation grows, Zrb periodically summarizes previous turns to keep the context concise and efficient.

3.  **Recent History**: A sliding window of the most recent messages, preserved in verbatim for immediate context.

These components are combined into the system prompt, giving the LLM a rich understanding of your project and goals.

## Basic Usage

### `LLMTask` (Programmatic)

```python
from zrb import LLMTask, cli

# Create a task that asks an LLM a question
chat_task = LLMTask(
    name="ask-ai",
    description="Ask a question to the AI",
    message="Tell me a fun fact about Python programming",
    system_prompt="You are a helpful and cheerful programming assistant."
)
cli.add_task(chat_task)
```

### `LLMChatTask` (Interactive)

The built-in `llm chat` task is an instance of `LLMChatTask`. You can run it via the CLI:

```bash
zrb llm chat
```

Inside the chat, you can use slash commands:
- `/save <name>`: Save the current session.
- `/load <name>`: Load a saved session.
- `/attach <path>`: Attach a file to the conversation.
- `/yolo`: Toggle YOLO mode (execute tools without confirmation).
- `/redirect <path>` or `> <path>`: Save the last AI response to a file.
- `/compress`: Manually trigger history summarization.
- `! <command>`: Execute a shell command directly.
- `/help`: Show all available commands.

## Tools and Subagents

The real power of LLM tasks comes from "tools"—Python functions the LLM can call to perform actions.

### Providing a Simple Tool

```python
from zrb import LLMTask, cli

def get_weather(location: str) -> str:
    """Get the current weather for a specific location."""
    # In a real scenario, this would call a weather API
    return f"The weather in {location} is sunny and 25°C."

weather_chat = LLMTask(
    name="weather-chat",
    description="Chat about the weather",
    message="What's the weather like in New York?",
    tools=[get_weather]
)
cli.add_task(weather_chat)
```

### Subagents: Agents as Tools

You can delegate complex sub-problems to specialized agents using subagent tools.

```python
from zrb import LLMTask, cli
from zrb.llm.tool.sub_agent import create_sub_agent_tool
from zrb.llm.tool.web import open_web_page

# Create a subagent tool that is an expert at fetching news
it_news_fetcher_tool = create_sub_agent_tool(
    name="it_news_fetcher",
    description="Fetches the latest IT news from Hacker News.",
    system_prompt="You are a Hacker News fetcher. You load and curate news from http://news.ycombinator.com.",
    tools=[open_web_page]
)

# Create a main LLMTask that can use the subagent
llm_chat_with_subagent = cli.add_task(
    LLMTask(
        name="llm-chat-subagent",
        description="Chat with an LLM that can fetch IT news",
        message="What is the latest IT news?",
        tools=[it_news_fetcher_tool]
    )
)
```

## Global LLM Configuration

You can set default configurations for all LLM tasks using the `llm_config` object.

```python
from zrb.llm.config.config import llm_config

# Set a default model name
llm_config.model = "openai:gpt-4o"

# Use a custom base URL (e.g., for Ollama)
llm_config.base_url = "http://localhost:11434/v1"
```

**When to use**: Use `LLMTask` for automated AI steps in your pipelines. Use `LLMChatTask` (or `zrb llm chat`) when you need an interactive, tool-aware assistant for development, research, or troubleshooting.

For advanced integration, see the [Customizing the AI Assistant](../../../advanced-topics/customizing-ai-assistant.md) guide.
