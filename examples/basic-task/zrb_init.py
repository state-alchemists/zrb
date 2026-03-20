"""
Basic Task Example

Shows how to create simple tasks with inputs and actions.
"""

from zrb import IntInput, StrInput, Task, cli

# =============================================================================
# Task with Lambda Action
# =============================================================================

hello = cli.add_task(
    Task(
        name="hello",
        description="Say hello to someone",
        input=[StrInput(name="name", description="Your name", default="World")],
        action=lambda ctx: f"Hello, {ctx.input.name}!",
    )
)

# =============================================================================
# Task with String Template Action
# =============================================================================

greet = cli.add_task(
    Task(
        name="greet",
        description="Greet someone with a template",
        input=[StrInput(name="name", default="Friend")],
        action="Greetings, {ctx.input.name}! Welcome to Zrb.",
    )
)

# =============================================================================
# Task with Multiple Inputs
# =============================================================================

add_task = cli.add_task(
    Task(
        name="add",
        description="Add two numbers",
        input=[
            IntInput("a", description="First number", default=0),
            IntInput("b", description="Second number", default=0),
        ],
        action="{ctx.input.a + ctx.input.b}",
    )
)

# =============================================================================
# Task with Function Action (using make_task decorator)
# =============================================================================

from zrb import make_task


@make_task(
    name="multiply",
    description="Multiply two numbers",
    input=[
        IntInput("a", description="First number", default=1),
        IntInput("b", description="Second number", default=1),
    ],
)
def multiply(ctx):
    result = ctx.input.a * ctx.input.b
    ctx.print(f"Calculating {ctx.input.a} × {ctx.input.b}")
    return result


# =============================================================================
# Task with Dynamic Default Value
# =============================================================================

from zrb import FloatInput

calculate_total = cli.add_task(
    Task(
        name="total",
        description="Calculate total with tax",
        input=[
            FloatInput(
                name="price",
                prompt="Original price",
                default=100,
            ),
            FloatInput(
                name="tax_rate",
                prompt="Tax rate (%)",
                default=12,
            ),
        ],
        action=lambda ctx: ctx.input.price * (1 + ctx.input.tax_rate / 100),
    )
)
