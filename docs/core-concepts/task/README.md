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

### 3. Controlling The Flow: Dependencies and Chains

Zrb provides a powerful system for controlling the order of execution and handling success or failure. You can define dependencies between tasks to build complex, resilient workflows.

#### Upstream (Prerequisites)

An `upstream` task is a prerequisite that must complete successfully before the current task can run.

```python
from zrb import Task, cli

setup = Task(name="setup", action=lambda ctx: print("Setting up..."))
main_task = Task(name="main-task", action=lambda ctx: print("Main task running."))

# Define 'setup' as an upstream for 'main_task'
main_task.add_upstream(setup)

# Or, more elegantly, use the `<<` operator
main_task << setup

# For sequential chains, the `>>` operator is often more readable
# This means 'main_task' becomes an upstream for 'teardown'
teardown = Task(name="teardown", action=lambda ctx: print("Tearing down..."))
main_task >> teardown

# All three tasks are now chained: setup -> main_task -> teardown
cli.add_task(setup, main_task, teardown)
```
When you run `zrb teardown`, Zrb automatically runs `setup`, then `main_task`, and finally `teardown`.

#### Fallback (Error Handling)

A `fallback` task is executed only if the main task fails. This is perfect for cleanup operations or sending notifications.

```python
from zrb import CmdTask, cli

main_task = CmdTask(
    name="main-task",
    cmd="exit 1"  # This command will fail
)
cleanup_task = CmdTask(
    name="cleanup-task",
    cmd="echo 'Main task failed. Cleaning up...'"
)

# Set 'cleanup_task' as the fallback for 'main_task'
main_task.set_fallback(cleanup_task)
cli.add_task(main_task, cleanup_task)
```
Running `zrb main-task` will execute `main_task`, see it fail, and then automatically run `cleanup-task`.

#### Successor (On Success)

A `successor` task is executed only after the main task completes successfully. While similar to chaining with `>>`, it's useful for defining optional post-completion actions that aren't direct dependencies of other downstream tasks.

```python
from zrb import Task, cli

main_task = Task(
    name="main-task",
    action=lambda ctx: print("Main task completed successfully.")
)
notification_task = Task(
    name="notification-task",
    action=lambda ctx: print("Notifying team about success.")
)

# Set 'notification_task' as the successor for 'main_task'
main_task.set_successor(notification_task)
cli.add_task(main_task, notification_task)
```
Running `zrb main-task` will execute `main_task`, and upon its success, `notification_task` will be triggered.

### 4. Other Key Features

*   **`name`** & **`description`**: The task's identifier and human-readable explanation.
*   **`readiness_check`**: A sub-task that must succeed before the main task is considered "ready."
*   **`retries`**: The number of times to retry a task if it fails.
*   **`fallbacks`**: A list of tasks to run if the main task fails.
*   **`successors`**: A list of tasks to run after the main task succeeds.

## Advanced Task Features

Beyond the basics, Zrb tasks have powerful features for better integration and less boilerplate.

### Using Tasks as Python Functions

Every Zrb task can be converted into a regular Python function using the `.to_function()` method. This allows you to call a task from other Python scripts, just like any other function. Zrb automatically maps the task's `Input`s to function arguments.

```python
from zrb import CmdTask, StrInput

# Define a task
greet_task = CmdTask(
    name="greet",
    input=StrInput(name="name", default="world"),
    cmd="echo Hello, {ctx.input.name}"
)

# Convert it to a callable function
greet_fn = greet_task.to_function()

# Now you can call it from Python!
result = greet_fn(name="Zaruba")  # Sets the 'name' input
# This will print "Hello, Zaruba" to the console
```
This feature makes it easy to integrate your Zrb workflows with other Python applications or testing frameworks.

### Automatic Context Inheritance

To keep your code DRY (Don't Repeat Yourself), Zrb automatically makes the `Input`s and `Env`s of all upstream tasks available to downstream tasks. You only need to define a shared configuration once.

```python
from zrb import Task, StrInput, Env, cli

# Define an input and environment variable in a setup task
set_config = Task(
    name="set-config",
    input=StrInput(name="user", default="default-user"),
    env=Env(name="APP_HOST", default="localhost")
)

# This task can access 'user' and 'APP_HOST' without redefining them
use_config = Task(
    name="use-config",
    action=lambda ctx: print(
        f"User is {ctx.input.user}, and Host is {ctx.env.APP_HOST}"
    )
)

# Chain the tasks
set_config >> use_config

cli.add_task(set_config, use_config)
```
When you run `zrb use-config --user="my-user"`, Zrb first processes the `set-config` task, populating `ctx.input.user`. This context is then passed along to `use_config`, which can access the value seamlessly.

## Task Types

Zrb comes with a variety of specialized task types for common operations.

*   [**`BaseTask`**](./types/base-task.md): The foundational class for all tasks.
*   [**`Task`**](./types/task.md): An alias for `BaseTask`, used for general-purpose Python tasks.
*   [**`CmdTask`**](./types/cmd-task.md): For executing shell commands.
*   [**`HttpCheck`**](./types/http-check.md) & [**`TcpCheck`**](./types/tcp_check.md): For checking if services are ready.
*   [**`LLMTask`**](./types/llm-task.md): For interacting with Large Language Models.
*   [**`RsyncTask`**](./types/rsync-task.md): For synchronizing files.
*   [**`Scaffolder`**](./types/scaffolder.md): For generating files from templates.
*   [**`Trigger` and `Scheduler`**](./types/trigger-and-scheduler.md): For event-driven and scheduled tasks.

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