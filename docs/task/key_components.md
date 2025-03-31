# Key Components

## 1. Inputs

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

Inputs can be accessed in the task's action via the `ctx.input` object.

## 2. Environment Variables

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

### Env

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

### EnvMap

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

### EnvFile

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
```

## 3. Dependencies (Upstream Tasks)

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

## 4. Other Key Features

* **Name:** A unique identifier for the task (`name` property).
* **Description:** A human-readable explanation of the task's purpose (`description` property).
* **CLI Only:** Indicates whether the task is only executable from the command line (`cli_only` property).
* **Execute Condition:** A boolean attribute that determines whether the task should be executed.
* **Fallbacks:** A list of tasks that should be executed if this task fails (`fallbacks` property).
* **Successors:** A list of tasks that should be executed after this task completes successfully (`successors` property).
* **Readiness Checks:** Tasks that verify if a service or application is ready before proceeding with downstream tasks (`readiness_check` parameter). See [Readiness Checks](readiness_checks.md) for details.
* **Retries:** Specifies the number of times a task should be retried if it fails.

[Back to Task](README.md)