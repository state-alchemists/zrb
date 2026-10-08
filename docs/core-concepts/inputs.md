🔖 [Documentation Home](../README.md) > [Core Concepts](./) > Inputs

# User Inputs (Input)

Inputs make your tasks interactive and dynamic. They allow you to pass parameters to your tasks, whether from a user typing on the command line or from another task.

Inputs are distinct from environment variables; think of them as function arguments for your tasks, designed for values that change with each run.

> ⚠️ **Important:** Inputs are inherited transitively. If Task B depends on Task A, Task B has access to all inputs defined by Task A. When you run Task B, the CLI will prompt for the required inputs of *both* tasks. Where two tasks declare the same input name, the upstream declaration is the one used.

---

## Table of Contents

- [Basic Usage](#basic-usage)
- [Providing Inputs](#providing-inputs)
- [Available Input Types](#available-input-types)
- [Input Type Reference](#input-type-reference)
- [BoolInput Behavior](#boolinput-behavior)

---

## Basic Usage

Let's create a task that says hello to a specific person.

```python
from zrb import cli, CmdTask, StrInput, Tpl

cli.add_task(
  CmdTask(
    name="hello",
    input=[
      StrInput(name="name", description="The name to greet"),
      StrInput(name="prefix", description="A title to use", default="Mr./Ms."),
    ],
    # Access inputs via {ctx.input.<name>}
    cmd=Tpl("echo 'Hello {ctx.input.prefix} {ctx.input.name}'"),
  )
)
```

---

## Providing Inputs

Zrb gives you three ways to provide inputs:

### 1. Command-Line Flags

Zrb automatically generates CLI flags based on the input names.

```bash
zrb hello --name Edward --prefix Mr.
# Output: Hello Mr. Edward
```

### 2. Positional Arguments

By default (`allow_positional_parsing=True`, the default on every input), you can also supply values positionally, in the order the inputs were declared — no flag names needed.

```bash
zrb hello Edward Mr.
# Output: Hello Mr. Edward
```

### 3. Interactive Prompt

If you run the task without providing its inputs on the command line, Zrb uses `prompt_toolkit` to prompt you for each missing one — including inputs that have a default, unless you set `always_prompt=False` on them (then the default is used silently).

```bash
$ zrb hello
name: Edward
prefix [Mr./Ms.]: Dr.
Hello Dr. Edward
```

The prompt shows the input's `prompt=` text, falling back to its name, and a default in brackets (Enter accepts it).

---

## Available Input Types

Zrb provides concrete input classes for different data types. Always use these specific classes rather than the abstract `AnyInput` base class.

| Input Type | Description | Use Case |
|------------|-------------|----------|
| `StrInput` | Standard string text | Names, messages, paths |
| `IntInput` | Integer validation | Counts, ports, iterations |
| `FloatInput` | Floating-point numbers | Ratios, thresholds |
| `BoolInput` | Boolean flags | Enable/disable options |
| `PasswordInput` | Hidden input | Passwords, secrets, API keys |
| `OptionInput` | Selection from list | Predefined choices |
| `TextInput` | Multi-line text, edited in your editor | Commit messages, long prompts |

---

## Input Type Reference

### Comprehensive Example

```python
from zrb import Task, StrInput, IntInput, FloatInput, BoolInput, PasswordInput, OptionInput, cli

task = cli.add_task(
    Task(
        name="create-user",
        input=[
            StrInput(name="username", description="Account username"),
            PasswordInput(name="password", description="User password"),
            IntInput(name="age", description="User age", default=30),
            FloatInput(name="height", description="Height in meters", default=1.75),
            BoolInput(name="is-admin", description="Grant admin rights?", default=False),
            OptionInput(
                name="role",
                description="Primary system role",
                options=["viewer", "editor", "owner"],
                default="viewer"
            )
        ],
        action=lambda ctx: ctx.print(f"Creating user {ctx.input.username}...")
    )
)
```

---

## BoolInput Behavior

`BoolInput` has specific command-line behavior.

| To set | Command | Result |
|--------|---------|--------|
| `True` | `zrb create-user --username alice --is-admin` | Flag present = `True` |
| `False` | `zrb create-user --username alice --is-admin false` | Explicit value required |

> ⚠️ **Note:** The `--no-<flag>` syntax is **not** supported. Use `--flag false` instead.

---

## Quick Reference

Every input takes `name` (required) plus `description`, `prompt`, `default`, `allow_empty`, `allow_positional_parsing`, and `always_prompt`. Type-specific extras:

| Input Type | Extra Parameters |
|------------|------------------|
| `StrInput`, `IntInput`, `FloatInput`, `BoolInput`, `PasswordInput` | — |
| `OptionInput` | `options` (the allowed values) |
| `TextInput` | `editor`, `extension`, `comment_start`, `comment_end` |

An input name with dashes is also readable in snake_case: `is-admin` is `ctx.input.is_admin`.

---

🔖 [Documentation Home](../README.md) > [Core Concepts](./) > Inputs
