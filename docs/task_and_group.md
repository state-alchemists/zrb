# Task and Group

## Task

A Task represents a single unit of work within a ZRB project. It is defined by inheriting from `BaseTask` (or directly using the `Task` class) and encapsulates a specific action or set of actions that need to be performed. Tasks can range from running shell commands to executing Python code or interacting with LLMs.

### Key Features

*   **Name:** A unique identifier for the task (`name` property).
*   **Description:** A human-readable explanation of the task's purpose (`description` property).
*   **CLI Only:** Indicates whether the task is only executable from the command line (`cli_only` property).
*   **Inputs:** A list of `AnyInput` objects that define the inputs required by the task (`inputs` property).
*   **Environment Variables:** A list of `AnyEnv` objects that define the environment variables required by the task (`envs` property).
*   **Action:** The action to be performed by the task. This can be a shell command (using `CmdTask`), Python code (using `LLMTask` or a custom task), or any other executable action.
*   **Execute Condition:** A boolean attribute that determines whether the task should be executed.
*   **Dependencies (Upstreams):** A list of tasks that must be executed before this task can be executed (`upstreams` property).
*   **Fallbacks:** A list of tasks that should be executed if this task fails (`fallbacks` property).
*   **Successors:** A list of tasks that should be executed after this task completes successfully (`successors` property).
*   **Readiness Checks:** A list of tasks that are executed to determine if the task has completed successfully (`readiness_checks` property).
*   **Retries:** Specifies the number of times a task should be retried if it fails.

### Example

```python
from zrb import Task, CmdTask, StrInput

# Define a task that runs a shell command
my_task = CmdTask(
    name="my_task",
    description="This is an example task that runs a shell command.",
    cmd="echo 'Hello, world!'",
)

# Define a task with an input
my_task_with_input = CmdTask(
    name="my_task_with_input",
    description="This is an example task that takes an input.",
    cmd="echo {ctx.input.message}",
    input=StrInput(name="message", default="Hello, world!"),
)
```

## Group

A Group is a collection of tasks and subgroups that are organized together. Groups provide a way to structure and manage complex workflows. Groups are defined by inheriting from `AnyGroup` (or directly using the `Group` class).

### Key Features

*   **Name:** A unique identifier for the group (`name` property).
*   **Description:** A human-readable explanation of the group's purpose (`description` property).
*   **Subtasks:** A dictionary of tasks that belong to the group (`subtasks` property).
*   **Subgroups:** A dictionary of subgroups that belong to the group (`subgroups` property).

### Example

```python
from zrb import Group, Task, CmdTask

# Define a group
my_group = Group(
    name="my_group",
    description="This is an example group.",
)

# Add tasks to the group
task1 = CmdTask(name="task1", cmd="echo 'Task 1'")
task2 = CmdTask(name="task2", cmd="echo 'Task 2'")
my_group.add_task(task1)
my_group.add_task(task2)
```

## CLI

The `cli` module provides the command-line interface for ZRB. The `cli` object is an instance of the `Cli` class, which inherits from `Group`. This means that the `cli` object can contain tasks and subgroups, and it can be used to run tasks from the command line.

### Key Features

*   **Task Execution:** The `run` method is used to execute tasks from the command line.
*   **Group Management:** The `add_group` method is used to add subgroups to the CLI.
*   **Task Registration:** The `@make_task` decorator is used to register tasks with the CLI.

### Example

```python
from zrb import cli, Task, CmdTask

# Define a task
@cli.add_task
class MyTask(Task):
    name = "my_task"
    description = "This is an example task that is registered with the CLI."
    def run(self, ctx):
        print("Hello, world!")

# Or using the @make_task decorator
@make_task(name="my_other_task", description="This is another example task", group=cli)
def my_other_task(ctx):
    print("Hello from another task!")
```

## Usage

Tasks and groups are defined in Python code (typically in a `zrb_init.py` file). The ZRB runner will then execute the tasks and groups in the order specified by their dependencies. Tasks can be added to groups using the `add_task` method, and subgroups can be added to groups using the `add_group` method. Dependencies between tasks can be defined using the `>>` operator (e.g., `task1 >> task2` means that `task2` depends on `task1`). The `cli` object is used to register tasks and groups with the command-line interface, allowing them to be executed from the command line.