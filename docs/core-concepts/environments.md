🔖 [Documentation Home](../../README.md) > [Core Concepts](./) > Environments

# Environment Variables (Env)

In Zrb, environment variables (`Env`) are a powerful way to configure your tasks, manage secrets, and adapt your workflows to different deployment environments.

You can access environment variables within a task through the `ctx.env` object.

**Crucial Concept:** Like Inputs, `Env` definitions are inherited recursively. If Task B depends on Task A, Task B automatically loads and makes available all `Env`s required by Task A.

## The `Env` Object

The `Env` class is the most direct way to define an environment variable. It ensures the variable exists when the task runs.

```python
from zrb import cli, CmdTask, Env

cli.add_task(
  CmdTask(
    name="hello",
    env=[
      Env(name="USER", default="nobody"),
      Env(name="SHELL", default="sh"),
    ],
    # The variables are injected into the shell execution environment
    # and are also accessible via {ctx.env.<name>}
    cmd="echo 'Hello {ctx.env.USER}, your shell is {ctx.env.SHELL}'",
  )
)
```

### OS Integration

The `Env` object is highly configurable. It can link directly to OS-level environment variables.

```python
Env(
    name="API_KEY",       # Name of the variable accessed via ctx.env.API_KEY
    default="",           # Default value if not found
    link_to_os=True,      # Look for the variable in the OS environment
    os_name="MY_API_KEY"  # Optional: Use a different name when looking in the OS env
)
```
If `link_to_os` is True and the variable isn't in the OS, Zrb will use the `default` value provided (or an empty string if no default is specified). Unlike `Inputs`, `Env` objects **do not** interactively prompt for missing values.

## Multiple Variables: `EnvMap` and `EnvFile`

Defining dozens of variables individually can be tedious. Zrb provides tools for bulk definition.

### `EnvMap`
Define a dictionary of variables at once. You can also specify an `os_prefix` to automatically namespace your variables.

```python
from zrb import Task, EnvMap, cli

task = cli.add_task(
    Task(
        name="env-map-example",
        env=EnvMap(
            vars={
                "API_KEY": "default-key",
                "DEBUG": "false",
                "PORT": "8080"
            },
            link_to_os=True,      # Look for variables in the OS environment
            os_prefix="APP"       # It will look for APP_API_KEY, APP_DEBUG, etc.
        ),
        action=lambda ctx: ctx.print(f"API Key: {ctx.env.API_KEY}, Port: {ctx.env.PORT}")
    )
)
```

### `EnvFile` (.env integration)
For managing environment-specific configurations locally, use `.env` files. The `EnvFile` class automatically loads them.

```python
from zrb import Task, EnvFile, cli

# Assumes you have a .env file with:
# DB_PASSWORD=supersecret

task = cli.add_task(
    Task(
        name="db-connect",
        env=EnvFile(
            path=".env",          # Path to the .env file
            link_to_os=True       # Also look in the OS environment (OS env takes precedence)
        ),
        action=lambda ctx: ctx.print(f"Connecting with {ctx.env.DB_PASSWORD}")
    )
)
