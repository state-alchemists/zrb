🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Core Concepts](../README.md) > [Task](./README.md)

# The Task

A `Task` is the fundamental unit of work in Zrb. It's the "verb" of your automation, the action you want to perform. Tasks are the building blocks of your workflows, encapsulating everything from simple shell commands to complex Python logic or interactions with AI models.

> **Important**: A task is only runnable if it's registered with the `cli` or a `Group` that's attached to the `cli`. If you define a task but don't register it, Zrb won't know it exists!

## 3 Ways to Create a Task

Zrb offers three flexible ways to create tasks, each suited to different needs.

### 1. Direct Instantiation

The most straightforward method is to create an instance of a `Task` class directly.

```python
from zrb import Task, cli

my_task = Task(
    name="my-task",
    description="A simple task",
    action=lambda ctx: print("Hello, world!")
)
cli.add_task(my_task)  # Register it!
```

**When to use**: Perfect for simple tasks or when you need to create tasks programmatically (e.g., in a loop).

### 2. Class Definition

For more complex or reusable tasks, you can define your own task class.

```python
from zrb import Task, cli

# Define the class...
class MyTask(Task):
    def run(self, ctx):
        print("Hello, world!")

# ...then instantiate and register it
my_task = MyTask(name="my-task", description="A simple task")
cli.add_task(my_task)

# Or, use a decorator for a more concise approach
@cli.add_task
class AnotherTask(Task):
    name = "another-task"
    description = "Another simple task"
    
    def run(self, ctx):
        print("Hello from another task!")
```

**When to use**: Ideal for complex logic, when you want to use inheritance, or to create reusable task templates. It's a more organized, object-oriented approach.

### 3. Function Decorator

The most elegant way to create a task from a simple function is with the `@make_task` decorator.

```python
from zrb import make_task, cli

@make_task(
    name="my-task",
    description="A simple task",
    group=cli  # Register it directly in the decorator
)
def my_task(ctx):
    print("Hello, world!")
```

**When to use**: The best choice for tasks where the core logic fits neatly into a single function. It's clean, readable, and highly recommended for most common use cases.

## Anatomy of a Task

Tasks are more than just an action. They have several key components that make them powerful and flexible.

### 1. Inputs

Inputs make your tasks interactive and reusable. They allow you to pass parameters from the command line or web UI. For a deep dive, see the [Input documentation](../input/README.md).

```python
from zrb import Task, StrInput, IntInput, BoolInput, OptionInput, cli

task = Task(
    name="example-task",
    input=[
        StrInput(name="name", description="Your name", default="World"),
        IntInput(name="age", description="Your age", default=30),
        BoolInput(name="subscribe", description="Subscribe to newsletter?", default=True),
        OptionInput(
            name="color",
            description="Favorite color",
            options=["red", "green", "blue"],
            default="blue"
        )
    ],
    action=lambda ctx: print(f"Hello {ctx.input.name}, you are {ctx.input.age} years old.")
)
cli.add_task(task)
```

### 2. Environment Variables

Tasks can securely access configuration and secrets through environment variables. For more details, check the [Environment documentation](../env/README.md).

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

### 3. Dependencies (Upstream Tasks)

Tasks can depend on other tasks. An `upstream` task is a prerequisite that must complete successfully before the current task can run.

```python
from zrb import Task, cli

task1 = Task(name="task1", action=lambda ctx: print("Task 1"))
task2 = Task(name="task2", action=lambda ctx: print("Task 2"))

# task3 will only run after task1 and task2 are complete
task3 = Task(name="task3", upstream=[task1, task2], action=lambda ctx: print("Task 3"))

# You can also define dependencies with the `>>` operator
task1 >> task3
task2 >> task3

# Or chain them for sequential execution
task1 >> task2 >> task3  # task3 depends on task2, which depends on task1

cli.add_task(task1, task2, task3)
```

### 4. Other Key Features

*   **`name`** & **`description`**: The task's identifier and human-readable explanation.
*   **`readiness_check`**: A sub-task that must succeed before the main task is considered "ready."
*   **`retries`**: The number of times to retry a task if it fails.
*   **`fallbacks`**: A list of tasks to run if the main task fails.
*   **`successors`**: A list of tasks to run after the main task succeeds.

## Task Types

Zrb comes with a variety of specialized task types for common operations.

*   [**`BaseTask`**](./types/base-task.md): The foundational class for all tasks.
*   [**`Task`**](./types/task.md): An alias for `BaseTask`, used for general-purpose Python tasks.
*   [**`CmdTask`**](./types/cmd-task.md): For executing shell commands.
*   [**`HttpCheck`**](./types/http-check.md) & [**`TcpCheck`**](./types/tcp_check.md): For checking if services are ready.
*   [**`LLMTask`**](./types/llm-task.md): For interacting with Large Language Models.
*   [**`RsyncTask`**](./types/rsync-task.md): For synchronizing files.
*   [**`Scaffolder`**](./types/scaffolder.md): For generating files from templates.
*   [**`Scheduler`**](./types/scheduler.md): For triggering tasks on a schedule.

## Readiness Checks in Action

Readiness checks are a powerful feature for orchestrating workflows that involve services that take time to start up.

### `HttpCheck`

Wait for a web server to be ready before testing it.

```python
from zrb import CmdTask, HttpCheck, cli

start_server = cli.add_task(
    CmdTask(
        name="start-server",
        cmd="python -m http.server 8000",
        readiness_check=HttpCheck(name="check-server", url="http://localhost:8000")
    )
)

test_server = cli.add_task(
    CmdTask(name="test-server", cmd="curl http://localhost:8000")
)

start_server >> test_server
```

### `TcpCheck`

Wait for a database to accept connections before running migrations.

```python
from zrb import CmdTask, TcpCheck, cli

start_db = cli.add_task(
    CmdTask(
        name="start-db",
        cmd="docker compose up -d database",
        readiness_check=TcpCheck(name="check-db", host="localhost", port=5432)
    )
)

migrate_db = cli.add_task(
    CmdTask(name="migrate-db", cmd="python migrate.py")
)

start_db >> migrate_db
```

### Multiple Readiness Checks

You can specify multiple readiness checks for a single task:

```python
from zrb import CmdTask, HttpCheck, cli

# Start a microservices application and wait until all services are ready
start_app = cli.add_task(
    CmdTask(
        name="start-app",
        description="Start the application",
        cmd="docker compose up -d",
        readiness_check=[
            HttpCheck(name="check-api", url="http://localhost:3000/health"),
            HttpCheck(name="check-auth", url="http://localhost:3001/health"),
            HttpCheck(name="check-frontend", url="http://localhost:8080")
        ]
    )
)

# This task will only run after all services are ready
test_app = cli.add_task(
    CmdTask(
        name="test-app",
        description="Run integration tests",
        cmd="python test_integration.py"
    )
)

start_app >> test_app
```