🔖 [Documentation Home](../../README.md) > [Task](../README.md) > Complete Example
# Complete Example

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

[Back to Task](README.md)