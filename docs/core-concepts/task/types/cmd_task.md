🔖 [Documentation Home](../../../README.md) > [Task](../../../README.md) > [Core Concepts](../../README.md) > [Task](../README.md) > [Task Types](./README.md) > CmdTask

# `CmdTask`

The `CmdTask` is your go-to tool for running shell commands. It's a specialized task that makes it incredibly simple to execute external programs, run scripts, or perform any system-level operation.

## Examples

### Simple Command

```python
from zrb import CmdTask, cli

# A simple echo command
echo_task = CmdTask(
    name="echo",
    description="A classic echo command",
    cmd="echo 'Hello, from CmdTask!'"
)
cli.add_task(echo_task)
```

### Command with Input

You can easily make your commands dynamic by incorporating user input.

```python
from zrb import CmdTask, StrInput, cli

# Use figlet to create ASCII art from user input
figlet_task = CmdTask(
    name="figlet",
    description="Create ASCII art text",
    input=StrInput("message", description="Message to display", default="Hello"),
    cmd="figlet '{ctx.input.message}'"
)
cli.add_task(figlet_task)
```

### Command with Environment Variables

`CmdTask` also seamlessly integrates with environment variables, which is perfect for handling secrets like API keys.

```python
from zrb import CmdTask, Env, cli

# Call an API using a key from the environment
api_call_task = CmdTask(
    name="api-call",
    description="Call a protected API endpoint",
    env=[Env(name="API_KEY", default="")],
    cmd="curl -H 'Authorization: Bearer {ctx.env.API_KEY}' https://api.example.com/data"
)
cli.add_task(api_call_task)
```

**When to use**: Whenever you need to run a shell command. It's perfect for build scripts, system administration tasks, or interacting with any command-line tool.