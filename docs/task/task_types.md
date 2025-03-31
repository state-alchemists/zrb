# Task Types

Zrb provides several specialized task types for different use cases:

## 1. Task

The base implementation that can execute Python functions or expressions.

```python
from zrb import Task, IntInput, cli

# Using a lambda function
calculate_perimeter = Task(
    name="perimeter",
    description="Calculate perimeter of a square",
    input=[
        IntInput(name="height", description="Height"),
        IntInput(name="width", description="Width"),
    ],
    action=lambda ctx: 2 * (ctx.input.height + ctx.input.width),
)

# Using a string expression
calculate_area = Task(
    name="area",
    description="Calculate area of a square",
    input=[
        IntInput(name="height", description="Height"),
        IntInput(name="width", description="Width"),
    ],
    action="{ctx.input.height * ctx.input.width}",
)

cli.add_task(calculate_perimeter)
cli.add_task(calculate_area)
```

**When to use**: Use the base `Task` class when your task involves executing Python code, performing calculations, or any logic that doesn't fit into the more specialized task types. It's versatile and can handle most use cases.

## 2. CmdTask

A specialized task for executing shell commands.

```python
from zrb import CmdTask, StrInput, Env, cli

# Execute a simple shell command
echo_task = CmdTask(
    name="echo",
    description="Echo a message",
    cmd="echo 'Hello, world!'"
)

# Execute a command with input
figlet = CmdTask(
    name="figlet",
    description="Create ASCII art text",
    input=StrInput("message", description="Message to display"),
    cmd="figlet '{ctx.input.message}'"
)

# Execute a command with environment variables
api_call = CmdTask(
    name="api-call",
    description="Call an API",
    env=[Env(name="API_KEY", default="")],
    cmd="curl -H 'Authorization: Bearer {ctx.env.API_KEY}' https://api.example.com"
)

cli.add_task(echo_task)
cli.add_task(figlet)
cli.add_task(api_call)
```

**When to use**: Use `CmdTask` when you need to execute shell commands, run external programs, or interact with the system. It's perfect for tasks like running build commands, executing scripts, or performing system operations.

## 3. LLMTask

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

# Create an LLM task with tools
from pydantic_ai import Tool

def get_weather(location: str) -> str:
    """Get the weather for a location"""
    return f"The weather in {location} is sunny"

weather_chat = LLMTask(
    name="weather-chat",
    description="Chat about weather",
    message="What's the weather like in New York?",
    tools=[Tool(get_weather)]
)

cli.add_task(chat_task)
cli.add_task(weather_chat)
```

**When to use**: Use `LLMTask` when you need to integrate AI capabilities into your workflow. It's ideal for tasks like generating content, answering questions, summarizing text, or any other use case that benefits from language model capabilities.

## 4. Scaffolder

A task for creating files and directories from templates.

```python
from zrb import Scaffolder, StrInput, cli

# Create a project from a template
create_project = Scaffolder(
    name="create-project",
    description="Create a new project from a template",
    input=StrInput(name="project_name", description="Name of the project"),
    source_path="./templates/basic-project",
    destination_path="./projects/{ctx.input.project_name}",
    transform_content={"PROJECT_NAME": "{ctx.input.project_name}"}
)

cli.add_task(create_project)
```

**When to use**: Use `Scaffolder` when you need to generate files and directories from templates. It's perfect for tasks like creating new projects, generating boilerplate code, or setting up configuration files with customized content.

[Back to Task](README.md)