🔖 [Documentation Home](../../../README.md) > [Task](../../../README.md) > [Core Concepts](../../README.md) > [Task](../README.md) > [Task Types](./README.md) > Task

# `Task`

The `Task` class is the workhorse for running custom Python code within your Zrb workflows. It's an alias for `BaseTask`, providing a clean and direct way to execute Python functions or even simple expressions.

## Examples

### Using a Lambda Function

For short, simple actions, a `lambda` function is often the cleanest approach.

```python
from zrb import Task, IntInput, cli

# A task to calculate the perimeter of a rectangle
calculate_perimeter = Task(
    name="perimeter",
    description="Calculate the perimeter of a rectangle",
    input=[
        IntInput(name="height", description="Height of the rectangle"),
        IntInput(name="width", description="Width of the rectangle"),
    ],
    action=lambda ctx: 2 * (ctx.input.height + ctx.input.width),
)
cli.add_task(calculate_perimeter)
```

### Using a String Expression

For very simple calculations or operations, you can provide the action as a string expression. Zrb will evaluate it in the task's context.

```python
from zrb import Task, IntInput, cli

# A task to calculate the area of a rectangle
calculate_area = Task(
    name="area",
    description="Calculate the area of a rectangle",
    input=[
        IntInput(name="height", description="Height of the rectangle"),
        IntInput(name="width", description="Width of the rectangle"),
    ],
    action="{ctx.input.height * ctx.input.width}",
)
cli.add_task(calculate_area)
```

**When to use**: Use the base `Task` class whenever your logic is best expressed in Python. It's the most versatile task type, perfect for calculations, data manipulation, or any custom action that doesn't fit into the more specialized task types like `CmdTask` or `LLMTask`.