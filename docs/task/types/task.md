🔖 [Documentation Home](../../../README.md) > [Task](../../README.md) > Task Types > Task

# Task

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