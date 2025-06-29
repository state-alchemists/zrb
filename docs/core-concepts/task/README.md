🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Core Concepts](../README.md) > [Task](./README.md)

# Task

A Task represents a single unit of work within a Zrb project. Tasks are the fundamental building blocks of Zrb workflows, encapsulating specific actions that need to be performed. These actions can range from running shell commands to executing Python code or interacting with language models.

> **Important**: Only tasks that are registered to the CLI or its subgroups are accessible from the command line or web interface. Make sure to add your tasks to the CLI or a group that is added to the CLI.

## Creating Tasks

There are three main ways to create tasks in Zrb:

### 1. Direct instantiation

Create a task instance directly:

```python
from zrb import Task, cli

my_task = Task(
    name="my-task",
    description="A simple task",
    action=lambda ctx: print("Hello, world!")
)
cli.add_task(my_task)  # Register with CLI to make it accessible
```

Zrb provides several built-in task types (like `CmdTask`, `LLMTask`, `Scaffolder`, etc.) that you can directly instantiate.
Here are some commonly used built-in task types you can directly instantiate:

*   [`CmdTask`](./types/cmd_task.md): For executing shell commands.
*   [`LLMTask`](./types/llm_task.md): For integrating with Language Model APIs.
*   [`Scaffolder`](./types/scaffolder.md): For creating files and directories from templates.
*   [`RsyncTask`](./types/rsync_task.md): For synchronizing files and directories.
*   [`HttpCheck`](./types/http_check.md): For performing HTTP health checks.
*   [`TcpCheck`](./types/tcp_check.md): For performing TCP port health checks.
*   [`Scheduler`](./types/scheduler.md): For triggering tasks based on a schedule.

**When to use**: Best for simple tasks where you need to create and configure tasks programmatically. Good for dynamic task creation or when you need to create multiple similar tasks with slight variations.

### 2. Class definition

Create a custom task class:

```python
from zrb import Task, cli

# Method 1: Define class then instantiate
class MyTask(Task):
    def run(self, ctx):
        print("Hello, world!")

my_task = MyTask(
    name="my-task",
    description="A simple task"
)
cli.add_task(my_task)

# Method 2: Use decorator to register directly
@cli.add_task
class AnotherTask(Task):
    name = "another-task"
    description = "Another simple task"
    
    def run(self, ctx):
        print("Hello from another task!")
```

**When to use**: Ideal for complex tasks that need custom logic, inheritance, or when you want to create reusable task templates. This approach is more object-oriented and allows for better code organization in larger projects.

### 3. Function decorator

Use the `@make_task` decorator to turn a Python function into a Task:

```python
from zrb import make_task, cli

@make_task(
    name="my-task",
    description="A simple task",
    group=cli  # Register with CLI directly in the decorator
)
def my_task(ctx):
    print("Hello, world!")
```

**When to use**: The most concise approach, perfect for simple tasks where the main logic is a single function. This is often the most readable option for straightforward tasks and is recommended for beginners.

## Key Components

### 1. Inputs

Inputs allow tasks to receive parameters from users or other tasks. Zrb provides several input types:

```python
from zrb import Task, StrInput, IntInput, FloatInput, BoolInput, OptionInput, cli

task = Task(
    name="example-task",
    input=[
        StrInput(name="name", description="Your name", default="World"),
        IntInput(name="age", description="Your age", default=30),
        FloatInput(name="height", description="Your height in meters", default=1.75),
        BoolInput(name="subscribe", description="Subscribe to newsletter", default=True),
        OptionInput(
            name="color",
            description="Favorite color",
            options=["red", "green", "blue"],
            default="blue"
        )
    ],
    action=lambda ctx: print(f"Hello {ctx.input.name}, you are {ctx.input.age} years old")
)
cli.add_task(task)  # Don't forget to register the task
```

Inputs can be accessed in the task's action via the `ctx.input` object. For a comprehensive guide on all available input types and how to use them, refer to the [Inputs documentation](../../input.md).

### 2. Environment Variables

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

Environment variables can be accessed in the task's action via the `ctx.env` object. Zrb provides several ways to define environment variables, including `Env`, `EnvMap`, and `EnvFile`.

```python
from zrb import Env, EnvMap, EnvFile

# Basic Env linking to OS variable
my_env = Env(name='MY_VAR', default='default', link_to_os=True)

# EnvMap for multiple variables
my_env_map = EnvMap(vars={"VAR1": "value1", "VAR2": "value2"})

# EnvFile for loading from .env
my_env_file = EnvFile(path=".env")
```

For a comprehensive guide on defining environment variables using `Env`, `EnvMap`, and `EnvFile`, refer to the [Environment Variables documentation](../../env.md).

### 3. Dependencies (Upstream Tasks)

Tasks can depend on other tasks, creating a workflow where tasks are executed in a specific order:

```python
from zrb import Task, cli

task1 = Task(name="task1", action=lambda ctx: print("Task 1"))
task2 = Task(name="task2", action=lambda ctx: print("Task 2"))
task3 = Task(name="task3", action=lambda ctx: print("Task 3"))

# Method 1: Using the upstream parameter
task3 = Task(
    name="task3",
    upstream=[task1, task2],
    action=lambda ctx: print("Task 3")
)

# Method 2: Using the >> operator
task1 >> task3
task2 >> task3

# Method 3: Chain multiple dependencies
task1 >> task2 >> task3  # task3 depends on task2, which depends on task1

# Register all tasks with CLI
cli.add_task(task1)
cli.add_task(task2)
cli.add_task(task3)
```

When a task has upstream dependencies, it will only execute after all its upstream tasks have completed successfully.

### 4. Other Key Features

Beyond inputs, environment variables, and dependencies, tasks have several other key properties:

*   **Name:** A unique identifier for the task (`name` property). Used to reference the task from the CLI or other tasks.
*   **Description:** A human-readable explanation of the task's purpose (`description` property).
*   **CLI Only:** Indicates whether the task is only executable from the command line (`cli_only` property). If true, the task will not be available in the web interface.
*   **Execute Condition:** A boolean attribute (`execute_condition` property) that determines whether the task should be executed. This can be a simple boolean value or a Jinja2 template string that evaluates to true or false based on the context (e.g., inputs, environment variables).
*   **Fallbacks:** A list of tasks (`fallbacks` property) that should be executed if this task fails. Useful for defining alternative actions in case of errors.
*   **Successors:** A list of tasks (`successors` property) that should be executed after this task completes successfully. Similar to `upstream`, but defines tasks that run *after* the current task.
*   **Readiness Checks:** Tasks that verify if a service or application is ready before proceeding with downstream tasks (`readiness_check` parameter). See [Readiness Checks](#readiness-checks) for details.
*   **Retries:** Specifies the number of times a task should be retried if it fails (`retries` property). Helps in handling transient errors.

## Readiness Checks

Readiness checks are special tasks that verify if a service or application is ready before proceeding with downstream tasks. Readiness checks are themselves tasks, meaning you can use any task type suitable for verification, such as `HttpCheck` or a custom Python task. For more information on different task types, see the [Task Types section in the Task documentation](../README.md#task-types). This is particularly useful for tasks that start services, servers, or containers.

Zrb provides built-in readiness check tasks:

### HttpCheck

Verifies that an HTTP endpoint is responding with a 200 status code:

```python
from zrb import CmdTask, HttpCheck, cli

# Start a web server and wait until it's ready
start_server = cli.add_task(
    CmdTask(
        name="start-server",
        description="Start the web server",
        cmd="python -m http.server 8000",
        readiness_check=HttpCheck(
            name="check-server",
            url="http://localhost:8000"
        )
    )
)

# This task will only run after the server is ready
test_server = cli.add_task(
    CmdTask(
        name="test-server",
        description="Test the web server",
        cmd="curl http://localhost:8000"
    )
)

start_server >> test_server
```

### TcpCheck

Verifies that a TCP port is open and accepting connections:

```python
from zrb import CmdTask, TcpCheck, cli

# Start a database and wait until it's ready
start_database = cli.add_task(
    CmdTask(
        name="start-database",
        description="Start the database",
        cmd="docker compose up -d database",
        readiness_check=TcpCheck(
            name="check-database",
            host="localhost",
            port=5432
        )
    )
)

# This task will only run after the database is ready
migrate_database = cli.add_task(
    CmdTask(
        name="migrate-database",
        description="Run database migrations",
        cmd="python migrate.py"
    )
)

start_database >> migrate_database
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

### Readiness Check Parameters

When using readiness checks, you can configure their behavior with these parameters:

*   **readiness_check_delay**: The delay in seconds before starting readiness checks (default: 0.5)
*   **readiness_check_period**: The period in seconds between readiness checks (default: 5)
*   **readiness_failure_threshold**: The number of consecutive failures allowed before considering the task failed (default: 1)

```python
from zrb import CmdTask, HttpCheck, cli

# Start a web application with custom readiness check parameters
start_app = cli.add_task(
    CmdTask(
        name="start-app",
        description="Start the web application",
        cmd="npm start",
        readiness_check=HttpCheck(name="check-app", url="http://localhost:3000"),
        readiness_check_delay=2.0,  # Wait 2 seconds before starting checks
        readiness_check_period=10.0,  # Check every 10 seconds
        readiness_failure_threshold=3  # Allow up to 3 failures before failing
    )
)
```

### Custom Readiness Checks

You can create custom readiness checks by using any task type. A readiness check is considered successful if it completes without raising an exception.

```python
from zrb import Task, CmdTask, cli

# Custom readiness check that verifies a specific condition
check_database_initialized = Task(
    name="check-database-initialized",
    description="Check if the database is initialized",
    action=lambda ctx: ctx.run_command("psql -c 'SELECT 1 FROM users LIMIT 1'")
)

# Start a database and use the custom check
start_database = cli.add_task(
    CmdTask(
        name="start-database",
        description="Start the database",
        cmd="docker compose up -d database",
        readiness_check=check_database_initialized
    )
)
```

### How Readiness Checks Work

When a task with readiness checks completes:

1.  Zrb executes the readiness checks
2.  If all checks pass, the task is considered complete and downstream tasks can run
3.  If any check fails, Zrb will retry the checks according to the configured parameters
4.  The task will only be considered complete when all readiness checks pass

This ensures that downstream tasks only run when the system is in the expected state, preventing race conditions and timing issues.

## Complete Example

Here's a complete example that demonstrates various task features:

```python
from zrb import Task, CmdTask, StrInput, IntInput, Env, cli, make_task, Group

# Create a group for related tasks
math_group = Group(
    name="math",
    description="Mathematical operations"
)
cli.add_group(math_group)  # Register the group with CLI

# Define a task that runs a shell command
my_task = CmdTask(
    name="my_task",
    description="This is an example task that runs a shell command.",
    cmd="echo 'Hello, world!'",
)
cli.add_task(my_task)  # Register with CLI directly

# Define a task with an input
my_task_with_input = CmdTask(
    name="my_task_with_input",
    description="This is an example task that takes an input.",
    cmd="echo {ctx.input.message}",
    input=StrInput(name="message", default="Hello, world!"),
)
cli.add_task(my_task_with_input)

# Define a task with environment variables
my_task_with_env = CmdTask(
    name="my_task_with_env",
    description="This is an example task that uses environment variables.",
    cmd="echo 'API Key: {ctx.env.API_KEY}'",
    env=Env(name="API_KEY", default=""),
)
cli.add_task(my_task_with_env)

# Define a task with dependencies
my_dependent_task = Task(
    name="my_dependent_task",
    description="This task depends on my_task",
    action=lambda ctx: print("my_task has completed!"),
    upstream=my_task
)
cli.add_task(my_dependent_task)

# Or use the >> operator to define dependencies
my_task >> my_task_with_input

# Define a task using the @make_task decorator and add it to a group
@make_task(
    name="calculate_sum",
    description="Calculate the sum of two numbers",
    input=[
        IntInput(name="a", description="First number"),
        IntInput(name="b", description="Second number")
    ],
    group=math_group  # Add the task to the math group
)
def calculate_sum(ctx):
    return ctx.input.a + ctx.input.b