🔖 [Documentation Home](../../../README.md) > [Task](../../README.md) > [Task Types](../README.md) > CmdTask

# CmdTask

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