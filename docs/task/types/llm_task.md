🔖 [Documentation Home](../../../README.md) > [Task](../../README.md) > Task Types > LLMTask

# LLMTask

A task for interacting with language models.

```python
from zrb import LLMTask, cli

# Create a task that uses an LLM
chat_task = LLMTask(
    name="chat",
    description="Chat with an LLM",
    message="Tell me about Python programming",
    system_prompt="You are a helpful programming assistant"
)

# LLMTasks can be provided with "tools," which are functions or capabilities that the language model can use to perform actions or access external information.

def get_weather(location: str) -> str:
    """Get the weather for a location"""
    return f"The weather in {location} is sunny"

weather_chat = LLMTask(
    name="weather-chat",
    description="Chat about weather",
    message="What's the weather like in New York?",
    tools=[get_weather]
)

cli.add_task(chat_task)
cli.add_task(weather_chat)
```

### LLM Configuration

You can configure default settings for `LLMTask` instances using the `llm_config` object. This allows you to set a default model, API key, base URL, system prompt, and other parameters globally or for specific parts of your project.

```python
from zrb import llm_config

# Set a default model name
llm_config.set_default_model_name("gpt-4o")

# Set a default API key (consider using environment variables for secrets)
# llm_config.set_default_model_api_key("your-api-key")

# Set a default system prompt
llm_config.set_default_system_prompt("You are a helpful assistant.")

# You can also configure other settings like summarization and context enrichment thresholds
llm_config.set_default_history_summarization_threshold(10)
llm_config.set_default_enrich_context(True)
```

Settings configured via `llm_config` can be overridden by parameters provided directly to the `LLMTask` constructor.

### Subagents and `create_sub_agent_tool`

`LLMTask` supports the concept of subagents, which are specialized agents (essentially, other LLMTasks with their own configurations and tools) that can be used as tools by the main LLM. This allows you to delegate specific tasks or access specialized knowledge to a subagent, breaking down complex problems. You can create a subagent tool using the `create_sub_agent_tool` function.

`LLMTask` supports the concept of subagents, which are specialized agents that can be used as tools by the main LLM. This allows you to delegate specific tasks or access specialized knowledge to a subagent. You can create a subagent tool using the `create_sub_agent_tool` function.

Here's an example demonstrating how to add a subagent tool to an `LLMTask`:

```python
from zrb import LLMTask, cli
from zrb.builtin.llm.tool.sub_agent import create_sub_agent_tool
from zrb.builtin.llm.tool.web import open_web_page # Example tool for the subagent

# Define a subagent tool that fetches IT news
it_news_fetcher_tool = create_sub_agent_tool(
    tool_name="it_news_fetcher",
    tool_description="Fetch IT News",
    sub_agent_system_prompt="You are hacker news fetcher, You load and curate news from http://news.ycombinator.com, you start your response with REPORTING word",
    sub_agent_tools=[open_web_page] # The subagent can use the open_web_page tool
)

# Define an LLMTask that can use the subagent tool
llm_chat_with_subagent = cli.add_task(
    LLMTask(
        name="llm-chat-subagent",
        description="Chat with LLM that can fetch IT news",
        message="What is the latest IT news?",
        tools=[it_news_fetcher_tool] # Add the subagent tool to the LLMTask
    )
)

# The built-in llm_chat task also utilizes subagents and other advanced features.
```

**When to use**: Use `LLMTask` when you need to integrate AI capabilities into your workflow. It's ideal for tasks like generating content, answering questions, summarizing text, or any other use case that benefits from language model capabilities.