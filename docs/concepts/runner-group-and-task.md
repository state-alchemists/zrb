🔖 [Table of Contents](../README.md) / [Concepts](README.md)

# Runner, Group, and Task

Runner, task, and group are some pretty simple but important concepts. Let's see how they are related to each other.

# Runner

Any task registered to Zrb Runner will be accessible from the CLI. You can import Zrb Runner like the following:

```python
from zrb import runner
```

## Registering Tasks

Once you import a Zrb Runner, you can use it to register your task like the following:

```python
from zrb import runner, Task

task = Task(name='task')
runner.register(task)
```

To access the task, you can run the following command in your terminal:

```bash
zrb task
```

## Registering Grouped Tasks

You can also put your Task under Task Groups

```python
from zrb import runner, Task, Group

group = Group(name='group)
task = Task(name='task', group=group)
runner.register(task)
```

To access the grouped task, you can run the following command in your terminal:

```bash
zrb group task
```

## Restrictions

- You can only register a task once.
- Registered tasks cannot have the same names under the same group names.

Let's see some examples:

### Invalid Examples

The following example is invalid because you cannot register a task twice:

```python
from zrb import runner, Task

task = Task(name='task')
runner.register(task)
runner.register(task) # This yield error.
```

The following is invalid because the Tasks shared the same name:

```python
from zrb import runner, Task

task_1 = Task(name='task')
runner.register(task_1)

task_2 = Task(name='task')
runner.register(task_2) # This yield error.
```

The following is also invalid because the Tasks shared the same name and were under the same group name.

```python
from zrb import runner, Group, Task

group = Group(name='group')

task_1 = Task(name='task', group=group)
runner.register(task_1)

task_2 = Task(name='task', group=Group(name='group'))
runner.register(task_2) # This yield error.
```

### Valid Examples

```python
from zrb import runner, Task, Group

task_1 = Task(name='task')
runner.register(task_1)

task_2 = Task(name='task', group=Group(name='group'))
runner.register(task_2) # OK, task_1 and task_2 are located under different group
```

# Group

You can use Group to organize your Tasks. A Group will only be accessible from the CLI if at least one registered Task is under it.

You can also put a Group under another Group.

Let's see some examples:

```python
from zrb import runner, Task, Group

util = Group(name='util')
base64 = Group(name='base64', parent=util)

encode = Task(name='encode', group=base64)
runner.register(encode)

decode = Task(name='decode', group=base64)
runner.register(decode)
```

To access both `encode` and `decode`, you can use the following command from the CLI:

```bash
zrb util base64 encode
zrb util base64 decode
```

# Task

🔖 [Table of Contents](../README.md) / [Concepts](README.md)
