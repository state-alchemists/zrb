🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Core Concepts](../README.md) > [Env](./README.md)

# Env

Use `task`'s `env` to get environment variable values.

You can access `env` by using `ctx.env` property.

```python
from zrb import cli, CmdTask, Env

cli.add_task(
  CmdTask(
    name="hello",
    env=[
      Env(name="USER", default="nobody"),
      Env(name="SHELL", default="sh"),
    ],
    cmd="echo Hello {ctx.env.USER}, your shell is {ctx.env.sh}",
  )
)
```

You can invoke the task as follows

```sh
zrb hello
```

```
Hello gofrendi, your shell is zsh
```

This document explains how to define and access environment variables within your Zrb tasks. For information on configuring Zrb itself using environment variables, see the [Configuration guide](../../installation-and-configuration/configuration/README.md).

Environment variables allow tasks to access system or user-defined environment variables:

```python
from zrb import Task, Env, cli

task = Task(
    name="env-example",
    env=[
        Env(name="API_KEY", default="", link_to_os=True),
        Env(name="DEBUG", default="false", link_to_os=True)
    ],
    action=lambda ctx: print(f"API Key: {ctx.env.API_KEY}, Debug: {ctx.env.DEBUG}")
)
cli.add_task(task)
```

Environment variables can be accessed in the task's action via the `ctx.env` object.

Zrb provides several ways to define environment variables:

## Env

The basic environment variable class that links to OS environment variables:

```python
from zrb import Task, Env, cli

task = Task(
    name="env-example",
    env=Env(
        name="API_KEY",       # Name of the variable in ctx.env
        default="",           # Default value if not found in OS
        link_to_os=True,      # Whether to look for the variable in OS environment
        os_name="MY_API_KEY"  # Optional: custom OS environment variable name
    ),
    action=lambda ctx: print(f"API Key: {ctx.env.API_KEY}")
)
```

## EnvMap

Define multiple environment variables at once:

```python
from zrb import Task, EnvMap, cli

task = Task(
    name="env-map-example",
    env=EnvMap(
        vars={
            "API_KEY": "default-key",
            "DEBUG": "false",
            "PORT": "8080"
        },
        link_to_os=True,      # Whether to look for variables in OS environment
        os_prefix="APP"       # Optional: prefix for OS environment variables (APP_API_KEY, etc.)
    ),
    action=lambda ctx: print(f"API Key: {ctx.env.API_KEY}, Port: {ctx.env.PORT}")
)
```

## EnvFile

Load environment variables from a .env file:

```python
from zrb import Task, EnvFile, cli

task = Task(
    name="env-file-example",
    env=EnvFile(
        path=".env",          # Path to the .env file
        link_to_os=True,      # Whether to look for variables in OS environment
        os_prefix="APP"       # Optional: prefix for OS environment variables
    ),
    action=lambda ctx: print(f"API Key: {ctx.env.API_KEY}")
)