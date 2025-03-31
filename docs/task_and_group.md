# Task and Group

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

Inputs can be accessed in the task's action via the `ctx.input` object.

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

Environment variables can be accessed in the task's action via the `ctx.env` object.

Zrb provides several ways to define environment variables:

#### Env

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

#### EnvMap

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

#### EnvFile

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

* **Name:** A unique identifier for the task (`name` property).
* **Description:** A human-readable explanation of the task's purpose (`description` property).
* **CLI Only:** Indicates whether the task is only executable from the command line (`cli_only` property).
* **Execute Condition:** A boolean attribute that determines whether the task should be executed.
* **Fallbacks:** A list of tasks that should be executed if this task fails (`fallbacks` property).
* **Successors:** A list of tasks that should be executed after this task completes successfully (`successors` property).
* **Readiness Checks:** Tasks that verify if a service or application is ready before proceeding with downstream tasks (`readiness_check` parameter). See [Readiness Checks](#5-readiness-checks) for details.
* **Retries:** Specifies the number of times a task should be retried if it fails.

### 5. Readiness Checks

Readiness checks are special tasks that verify if a service or application is ready before proceeding with downstream tasks. This is particularly useful for tasks that start services, servers, or containers.

Zrb provides built-in readiness check tasks:

#### HttpCheck

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

#### TcpCheck

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

#### Multiple Readiness Checks

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

#### Readiness Check Parameters

When using readiness checks, you can configure their behavior with these parameters:

- **readiness_check_delay**: The delay in seconds before starting readiness checks (default: 0.5)
- **readiness_check_period**: The period in seconds between readiness checks (default: 5)
- **readiness_failure_threshold**: The number of consecutive failures allowed before considering the task failed (default: 1)

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

#### Custom Readiness Checks

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

#### How Readiness Checks Work

When a task with readiness checks completes:

1. Zrb executes the readiness checks
2. If all checks pass, the task is considered complete and downstream tasks can run
3. If any check fails, Zrb will retry the checks according to the configured parameters
4. The task will only be considered complete when all readiness checks pass

This ensures that downstream tasks only run when the system is in the expected state, preventing race conditions and timing issues.

## Task Types

Zrb provides several specialized task types for different use cases:

### 1. Task

The base implementation that can execute Python functions or expressions.

```python
from zrb import Task, IntInput, cli

# Using a lambda function
calculate_perimeter = Task(
    name="perimeter",
    description="Calculate perimeter of a square",
    input=[
        IntInput(name="height", description="Height"),
        IntInput(name="width", description="Width"),
    ],
    action=lambda ctx: 2 * (ctx.input.height + ctx.input.width),
)

# Using a string expression
calculate_area = Task(
    name="area",
    description="Calculate area of a square",
    input=[
        IntInput(name="height", description="Height"),
        IntInput(name="width", description="Width"),
    ],
    action="{ctx.input.height * ctx.input.width}",
)

cli.add_task(calculate_perimeter)
cli.add_task(calculate_area)
```

**When to use**: Use the base `Task` class when your task involves executing Python code, performing calculations, or any logic that doesn't fit into the more specialized task types. It's versatile and can handle most use cases.

### 2. CmdTask

A specialized task for executing shell commands.

```python
from zrb import CmdTask, StrInput, Env, cli

# Execute a simple shell command
echo_task = CmdTask(
    name="echo",
    description="Echo a message",
    cmd="echo 'Hello, world!'"
)

# Execute a command with input
figlet = CmdTask(
    name="figlet",
    description="Create ASCII art text",
    input=StrInput("message", description="Message to display"),
    cmd="figlet '{ctx.input.message}'"
)

# Execute a command with environment variables
api_call = CmdTask(
    name="api-call",
    description="Call an API",
    env=[Env(name="API_KEY", default="")],
    cmd="curl -H 'Authorization: Bearer {ctx.env.API_KEY}' https://api.example.com"
)

cli.add_task(echo_task)
cli.add_task(figlet)
cli.add_task(api_call)
```

**When to use**: Use `CmdTask` when you need to execute shell commands, run external programs, or interact with the system. It's perfect for tasks like running build commands, executing scripts, or performing system operations.

### 3. LLMTask

A task for interacting with language models.

```python
from zrb import LLMTask, cli

# Create a task that uses an LLM
chat_task = LLMTask(
    name="chat",
    description="Chat with an LLM",
    message="Tell me about Python programming",
    system_prompt="You are a helpful programming assistant"
)

# Create an LLM task with tools
from pydantic_ai import Tool

def get_weather(location: str) -> str:
    """Get the weather for a location"""
    return f"The weather in {location} is sunny"

weather_chat = LLMTask(
    name="weather-chat",
    description="Chat about weather",
    message="What's the weather like in New York?",
    tools=[Tool(get_weather)]
)

cli.add_task(chat_task)
cli.add_task(weather_chat)
```

**When to use**: Use `LLMTask` when you need to integrate AI capabilities into your workflow. It's ideal for tasks like generating content, answering questions, summarizing text, or any other use case that benefits from language model capabilities.

### 4. Scaffolder

A task for creating files and directories from templates.

```python
from zrb import Scaffolder, StrInput, cli

# Create a project from a template
create_project = Scaffolder(
    name="create-project",
    description="Create a new project from a template",
    input=StrInput(name="project_name", description="Name of the project"),
    source_path="./templates/basic-project",
    destination_path="./projects/{ctx.input.project_name}",
    transform_content={"PROJECT_NAME": "{ctx.input.project_name}"}
)

cli.add_task(create_project)
```

**When to use**: Use `Scaffolder` when you need to generate files and directories from templates. It's perfect for tasks like creating new projects, generating boilerplate code, or setting up configuration files with customized content.

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
```

# Group

A Group is a collection of tasks and subgroups that are organized together. Groups provide a way to structure and manage complex workflows. Groups are defined by inheriting from `AnyGroup` (or directly using the `Group` class).

> **Important**: Groups must be registered with the CLI (or a parent group that is registered with the CLI) for their tasks to be accessible from the command line or web interface.

## Key Features

*   **Name:** A unique identifier for the group (`name` property).
*   **Description:** A human-readable explanation of the group's purpose (`description` property).
*   **Subtasks:** A dictionary of tasks that belong to the group (`subtasks` property).
*   **Subgroups:** A dictionary of subgroups that belong to the group (`subgroups` property).

## Example

```python
from zrb import Group, Task, CmdTask, cli

# Define a group
my_group = Group(
    name="my_group",
    description="This is an example group.",
)
cli.add_group(my_group)  # Register the group with CLI

# Add tasks to the group
task1 = CmdTask(name="task1", cmd="echo 'Task 1'")
task2 = CmdTask(name="task2", cmd="echo 'Task 2'")
my_group.add_task(task1)
my_group.add_task(task2)

# Create a subgroup
my_subgroup = Group(
    name="my_subgroup",
    description="This is an example subgroup."
)
my_group.add_group(my_subgroup)  # Add subgroup to parent group

# Add a task to the subgroup
task3 = CmdTask(name="task3", cmd="echo 'Task 3'")
my_subgroup.add_task(task3)
```

# CLI

The `cli` module provides the command-line interface for Zrb. The `cli` object is an instance of the `Cli` class, which inherits from `Group`. This means that the `cli` object can contain tasks and subgroups, and it can be used to run tasks from the command line.

> **Important**: Only tasks that are registered to the CLI or its subgroups are accessible from the command line or web interface. Always make sure to add your tasks to the CLI or a group that is added to the CLI.

## Key Features

*   **Task Execution:** The `run` method is used to execute tasks from the command line.
*   **Group Management:** The `add_group` method is used to add subgroups to the CLI.
*   **Task Registration:** The `add_task` method or `@make_task` decorator is used to register tasks with the CLI.

## Example

```python
from zrb import cli, Task, CmdTask, Group, make_task

# Define a task and register it with CLI
@cli.add_task
class MyTask(Task):
    name = "my_task"
    description = "This is an example task that is registered with the CLI."
    def run(self, ctx):
        print("Hello, world!")

# Or using the @make_task decorator
@make_task(
    name="my_other_task", 
    description="This is another example task", 
    group=cli
)
def my_other_task(ctx):
    print("Hello from another task!")

# Create a group and register it with CLI
my_group = Group(
    name="my_group",
    description="This is an example group."
)
cli.add_group(my_group)

# Add a task to the group
my_group.add_task(
    CmdTask(
        name="group_task",
        description="This task belongs to my_group",
        cmd="echo 'Hello from my_group!'"
    )
)
```

## Task Accessibility

To make a task accessible from the command line or web interface, it must be registered with the CLI or a group that is registered with the CLI. Here are the ways to register tasks:

1. **Direct registration with CLI**:
   ```python
   cli.add_task(my_task)
   ```

2. **Using the `@make_task` decorator with `group=cli`**:
   ```python
   @make_task(name="my_task", group=cli)
   def my_task(ctx):
       # Task implementation
   ```

3. **Adding to a group that is registered with CLI**:
   ```python
   my_group = Group("my_group")
   cli.add_group(my_group)
   my_group.add_task(my_task)
   ```

## Usage

Tasks and groups are defined in Python code (typically in a `zrb_init.py` file). The Zrb runner will then execute the tasks and groups in the order specified by their dependencies. Tasks can be added to groups using the `add_task` method, and subgroups can be added to groups using the `add_group` method. Dependencies between tasks can be defined using the `>>` operator (e.g., `task1 >> task2` means that `task2` depends on `task1`). The `cli` object is used to register tasks and groups with the command-line interface, allowing them to be executed from the command line.