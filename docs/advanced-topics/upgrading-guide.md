🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Upgrading Guide

# Upgrading Guide from 0.x.x to 1.x.x

Zrb 1.x.x introduced significant changes and improvements over the 0.x.x series. This guide will help you migrate your existing Zrb task definitions from the old structure to the new one.

The core concepts of Tasks, Groups, and dependencies remain, but their definition and registration methods have been streamlined and unified under the `cli` object.

---

## Table of Contents

- [Key Changes Summary](#key-changes-summary)
- [Session and Context](#session-and-context)
- [Migration Examples](#migration-examples)
- [Parameter Renames](#parameter-renames)
- [Quick Reference](#quick-reference)

---

## Key Changes Summary

| 0.x.x | 1.x.x | Description |
|-------|-------|-------------|
| `runner` | `cli` | Task registration object |
| `runner.register()` | `cli.add_task()` | Registration method |
| `@python_task` | `@make_task` | Decorator name |
| `run` | `action` | Task execution parameter |
| `envs` | `env` | Environment variables |
| `upstreams` | `upstream` | Dependencies |
| `should_execute` | `execute_condition` | Conditional execution |
| `task.print_out()` | `ctx.print()` | Output method |

---

## Session and Context

Zrb 1.x.x introduces the concepts of `Session` and `Context`. Each task run operates within its own `Session`, providing isolation. The `Context` object, passed to task actions, contains session-specific information, including environment variables, inputs, and access to utilities like `ctx.print`.

---

## Migration Examples

### Basic Task Registration

**0.x.x:**
```python
from zrb import Task, runner

hello_task = Task(
    name='hello',
    run=lambda ctx: print("Hello from 0.x.x!")
)
runner.register(hello_task)
```

**1.x.x:**
```python
from zrb import Task, cli

hello_task = cli.add_task(
    Task(
        name='hello',
        action=lambda ctx: print("Hello from 1.x.x!")
    )
)
```

### Group Registration

**0.x.x:**
```python
from zrb import Group, Task, runner

parent_group = Group('parent')
child_group = Group('child', parent=parent_group)
my_task = Task(group=child_group, ...)
runner.register(parent_group)
```

**1.x.x:**
```python
from zrb import Group, Task, cli

parent_group = cli.add_group(Group('parent'))
child_group = parent_group.add_group(Group('child'))
my_task = child_group.add_task(Task(...))
```

### Decorator Pattern

**0.x.x:**
```python
from zrb import python_task, runner

@python_task(name='my-task')
def my_task(*args, **kwargs):
    task = kwargs.get('_task')
    task.print_out('Ok')

runner.register(my_task)
```

**1.x.x:**
```python
from zrb import make_task, cli

@make_task(name='my-task', group=cli)
def my_task(ctx):
    ctx.print('Ok')
```

### Environment Variables

**0.x.x:**
```python
from zrb import CmdTask, Env, EnvFile

task = CmdTask(
    envs=[Env(name='MY_VAR', default='value')],
    env_files=[EnvFile(path='.env')]
)
```

**1.x.x:**
```python
from zrb import CmdTask, Env, EnvFile

task = CmdTask(
    env=[
        Env(name='MY_VAR', default='value'),
        EnvFile(path='.env')
    ]
)
```

### Upstream Dependencies

**0.x.x:**
```python
from zrb import Task, runner

task1 = Task(name='task1', ...)
task2 = Task(name='task2', upstreams=[task1], ...)
runner.register(task1)
runner.register(task2)
```

**1.x.x:**
```python
from zrb import Task, cli

task1 = Task(name='task1', ...)
task2 = Task(name='task2', upstream=[task1], ...)
cli.add_task(task1)
cli.add_task(task2)

# Or using the >> operator:
# task1 >> task2
```

### CmdPath

**0.x.x:**
```python
from zrb import CmdTask

task = CmdTask(cmd_path=os.path.join("dir", "command.sh"))
```

**1.x.x:**
```python
from zrb import CmdTask, CmdPath

task = CmdTask(cmd=CmdPath(os.path.join("dir", "command.sh")))
```

---

## Parameter Renames

| 0.x.x Parameter | 1.x.x Parameter | Notes |
|-----------------|-----------------|-------|
| `run` | `action` | Task execution function |
| `envs` | `env` | Now accepts single or list |
| `env_files` | `env` (merged) | Use `EnvFile` in `env` list |
| `upstreams` | `upstream` | Now accepts single or list |
| `should_execute` | `execute_condition` | Conditional execution |
| `parent` | *(removed)* | Use `add_group()` instead |

---

## Quick Reference

```python
# 0.x.x → 1.x.x Migration Checklist

# 1. Update imports
- from zrb import runner    → from zrb import cli
- from zrb import python_task → from zrb import make_task

# 2. Update registration
- runner.register(task)     → cli.add_task(task)
- Group('name', parent=g)   → g.add_group(Group('name'))

# 3. Update parameters
- run=...                   → action=...
- envs=[...]                → env=[...]
- upstreams=[...]           → upstream=[...]
- should_execute=...        → execute_condition=...

# 4. Update decorators
- @python_task              → @make_task
- group=cli in decorator    → Register directly with cli

# 5. Update output
- task.print_out('msg')     → ctx.print('msg')
```

---