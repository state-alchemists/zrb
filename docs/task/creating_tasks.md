# Creating Tasks

There are three main ways to create tasks in Zrb:

## 1. Direct instantiation

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

## 2. Class definition

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

## 3. Function decorator

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

🔖 [Documentation Home](../../README.md) > [Task](../README.md) > Creating Tasks