🔖 [Documentation Home](../../../../README.md) > [Core Concepts](../../../README.md) > [Task](../../README.md) > [Task Types](./README.md) > LLMTask

# `LLMTask`

The `LLMTask` brings the power of Large Language Models (LLMs) directly into your Zrb workflows. It's a specialized task for interacting with AI, allowing you to generate content, answer questions, or even give your automations complex reasoning capabilities.

At its core, `LLMTask` is designed to be a stateful, context-aware agent. It manages conversation history and context to provide more relevant and intelligent responses over time.

## Context and History Management

`LLMTask` uses a sophisticated system to manage the context of a conversation, which is divided into three main parts:

1.  **Long-Term Context**: A Markdown-formatted string that stores stable, long-term information. This can include user preferences, project details, or any other facts that should persist across multiple conversations. This context is automatically curated by an LLM to add, update, and remove information as the conversation evolves.

2.  **Conversation Summary**: A narrative summary of the conversation history. As the conversation grows, an LLM periodically summarizes the turns to keep the immediate context concise and relevant.

3.  **Recent History**: A list of the most recent turns in the conversation. This provides the immediate context for the LLM's next response.

These three components are combined and sent to the LLM as part of the system prompt, giving it a rich understanding of the user's goals and the conversation's history.

## Basic Usage

```python
from zrb import LLMTask, cli

# Create a task that asks an LLM a question
chat_task = LLMTask(
    name="chat",
    description="Chat with an LLM",
    message="Tell me a fun fact about Python programming",
    system_prompt="You are a helpful and cheerful programming assistant."
)
cli.add_task(chat_task)
```

## Tools and Subagents

The real power of `LLMTask` comes from giving it "tools"—Python functions that the LLM can decide to use to get more information or perform actions.

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

You can even provide other, more specialized `LLMTask` instances as tools. This is called using a "subagent." It's a powerful pattern for delegating complex sub-problems.

```python
from zrb import LLMTask, cli
from zrb.builtin.llm.tool.sub_agent import create_sub_agent_tool
from zrb.builtin.llm.tool.web import open_web_page # An example built-in tool

# Create a subagent tool that is an expert at fetching IT news
it_news_fetcher_tool = create_sub_agent_tool(
    tool_name="it_news_fetcher",
    tool_description="Fetches the latest IT news from Hacker News.",
    sub_agent_system_prompt="You are a Hacker News fetcher. You load and curate news from http://news.ycombinator.com.",
    sub_agent_tools=[open_web_page] # The subagent can use the web page tool
)

# Create a main LLMTask that can use the subagent
llm_chat_with_subagent = cli.add_task(
    LLMTask(
        name="llm-chat-subagent",
        description="Chat with an LLM that can fetch IT news",
        message="What is the latest IT news?",
        tools=[it_news_fetcher_tool] # Give the main agent the subagent tool
    )
)
```

## Global LLM Configuration

You can set default configurations for all `LLMTask` instances using the `llm_config` object. This is useful for setting the API key and model for your entire project.

```python
from zrb import llm_config

# Set a default model name (e.g., "gpt-4o", "gemini-pro")
llm_config.set_default_model_name("gpt-4o")

# Set a default API key (best practice is to use an environment variable)
# llm_config.set_default_model_api_key("your-api-key")

# Set a default system prompt
llm_config.set_default_system_prompt("You are a helpful assistant.")
```

**When to use**: Use `LLMTask` whenever you want to add AI capabilities to your workflows. It's perfect for content generation, summarization, complex decision-making, and building AI-powered tools.