🔖 [Documentation Home](../../README.md) > [Core Concepts](./) > CLI & Groups

# CLI Integration & Grouping

Zrb is fundamentally designed for the command line. You don't just build a pipeline; you build a fully functional CLI application for your team. Every task you create can be instantly invoked from your terminal.

---

## Table of Contents

- [The `cli` Object](#the-cli-object)
- [Grouping Tasks (`Group`)](#grouping-tasks-group)
- [Group & Task Aliases](#group--task-aliases)
- [Removing Tasks and Groups](#removing-tasks-and-groups)

---

## The `cli` Object

The `cli` object (imported via `from zrb import cli`) is the root of your application. When you type `zrb` in your terminal, it executes this root group.

Whenever you add a task directly to the `cli`, Zrb automatically creates a command for it.

```python
from zrb import cli, CmdTask

cli.add_task(
    CmdTask(name="deploy_app", cmd="echo 'Deploying!'")
)
```

> 💡 **Tip:** Zrb automatically converts `snake_case` task names to `kebab-case` CLI commands!

```bash
zrb deploy-app
```

---

## Grouping Tasks (`Group`)

As your automation grows, having 50 commands at the root level becomes messy. Zrb allows you to organize tasks into logical `Group`s.

Groups act like sub-commands in standard CLI applications (e.g., `git commit`, `git push`, where `git` is the root, and `commit`/`push` are commands inside a group).

### Basic Grouping

```python
from zrb import cli, Group, CmdTask

# Create a group and add it to the root CLI
docker_group = cli.add_group(Group(name="docker", description="Manage containers"))

# Add tasks directly to the group
docker_group.add_task(CmdTask(name="build", cmd="docker build ."))
docker_group.add_task(CmdTask(name="run", cmd="docker run my-app"))
```

Now your CLI is organized into subcommands:

```bash
zrb docker build
zrb docker run
```

### Deep Nesting

Groups can be nested infinitely. You can add a group inside another group!

```python
from zrb import cli, Group, CmdTask

cloud_group = cli.add_group(Group(name="cloud"))
aws_group = cloud_group.add_group(Group(name="aws"))

aws_group.add_task(CmdTask(name="deploy", cmd="aws s3 sync ..."))
```

**Execution:** `zrb cloud aws deploy`

---

## Group & Task Aliases

You can provide aliases when adding a task or a group. This is useful if you want the command name to differ from the Python object name, or if you want multiple ways to call the same task.

```python
from zrb import cli, CmdTask

task = CmdTask(name="remove-all-containers", cmd="docker rm -f $(docker ps -aq)")

# Add to CLI with an alias
cli.add_task(task, alias="rm-all")
```

Now you can execute it quickly:

```bash
zrb rm-all
```

---

## Removing Tasks and Groups

If you are overriding a default `zrb_init.py` (e.g., from a parent directory) and want to hide certain inherited commands, you can remove them:

```python
from zrb import cli

# Assuming a 'legacy-deploy' task was added in a parent directory's zrb_init.py
cli.remove_task("legacy-deploy")
cli.remove_group("old-tools")
```

---

## Quick Reference

| Operation | Code |
|-----------|------|
| Add task to root | `cli.add_task(task)` |
| Create group | `cli.add_group(Group(name="name"))` |
| Add task to group | `group.add_task(task)` |
| Add task with alias | `cli.add_task(task, alias="short")` |
| Remove task | `cli.remove_task("task-name")` |
| Remove group | `cli.remove_group("group-name")` |

---