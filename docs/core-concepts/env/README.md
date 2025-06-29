🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Core Concepts](../README.md) > [Env](./README.md)

# Environment Variables (Env)

In Zrb, environment variables are a powerful way to configure your tasks, manage secrets, and adapt your workflows to different environments (like development, testing, and production).

You can access environment variables within a task through the `ctx.env` object.

> **Note:** This document focuses on defining and using environment variables within your tasks. For configuring Zrb itself, see the [Configuration guide](../../installation-and-configuration/configuration/README.md).

## A Simple Example

Let's start with a basic example. Here's a task that greets the current user, whose name is fetched from an environment variable.

```python
from zrb import cli, CmdTask, Env

cli.add_task(
  CmdTask(
    name="hello",
    env=[
      Env(name="USER", default="nobody"),
      Env(name="SHELL", default="sh"),
    ],
    cmd="echo 'Hello {ctx.env.USER}, your shell is {ctx.env.SHELL}'",
  )
)
```

When you run `zrb hello`, Zrb will look for the `USER` and `SHELL` environment variables on your system and substitute them into the command. If they aren't found, it will use the default values.

```sh
$ zrb hello
Hello your_username, your shell is /bin/zsh
```

## Ways to Define Environment Variables

Zrb offers a flexible system for defining environment variables.

### `Env`: The Basic Building Block

The `Env` class is the most direct way to define an environment variable. It's highly configurable, allowing you to link to OS environment variables, set defaults, and even use a different name in your task's context.

```python
from zrb import Task, Env, cli

task = Task(
    name="env-example",
    env=Env(
        name="API_KEY",       # Name of the variable in ctx.env
        default="",           # Default value if not found
        link_to_os=True,      # Look for the variable in the OS environment
        os_name="MY_API_KEY"  # Optional: custom OS environment variable name
    ),
    action=lambda ctx: print(f"API Key: {ctx.env.API_KEY}")
)
cli.add_task(task)
```

### `EnvMap`: For Multiple Variables

When you have several environment variables to define, `EnvMap` is your friend. It lets you define a dictionary of variables at once. You can also specify a prefix for the OS environment variables, which is great for namespacing your application's settings.

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
        link_to_os=True,      # Look for variables in the OS environment
        os_prefix="APP"       # Optional: prefix for OS variables (e.g., APP_API_KEY)
    ),
    action=lambda ctx: print(f"API Key: {ctx.env.API_KEY}, Port: {ctx.env.PORT}")
)
cli.add_task(task)
```

### `EnvFile`: Loading from `.env` Files

For managing environment-specific configurations, it's common practice to use `.env` files. The `EnvFile` class makes this a breeze. Simply point it to your `.env` file, and Zrb will load the variables for your task.

```python
from zrb import Task, EnvFile, cli

# Assumes you have a .env file with:
# API_KEY=your_secret_key

task = Task(
    name="env-file-example",
    env=EnvFile(
        path=".env",          # Path to the .env file
        link_to_os=True,      # Also look for variables in the OS environment
        os_prefix="APP"       # Optional: prefix for OS variables
    ),
    action=lambda ctx: print(f"API Key: {ctx.env.API_KEY}")
)
cli.add_task(task)
```

By combining these tools, you can create a robust and flexible configuration system for your Zrb tasks.