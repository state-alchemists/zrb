"""
Task Groups Example

Shows how to organize tasks in groups (like subcommands).
"""

from zrb import Group, IntInput, Task, cli

# =============================================================================
# Create a Group
# =============================================================================

# Groups act like subcommands
math = cli.add_group(Group("math", description="➕ Math tools"))

# =============================================================================
# Add Tasks to Group
# =============================================================================

math.add_task(
    Task(
        name="add",
        description="Add two numbers",
        input=[
            IntInput("a", description="First number", default=0),
            IntInput("b", description="Second number", default=0),
        ],
        action=lambda ctx: ctx.input.a + ctx.input.b,
    )
)

math.add_task(
    Task(
        name="subtract",
        description="Subtract two numbers",
        input=[
            IntInput("a", description="First number", default=0),
            IntInput("b", description="Second number", default=0),
        ],
        action="{ctx.input.a - ctx.input.b}",
    )
)

# =============================================================================
# Nested Groups
# =============================================================================

geometry = math.add_group(Group("geometry", description="📐 Geometry tools"))

geometry.add_task(
    Task(
        name="perimeter",
        description="Calculate perimeter of a rectangle",
        input=[
            IntInput(name="height", description="Height", default=10),
            IntInput(name="width", description="Width", default=5),
        ],
        action=lambda ctx: 2 * (ctx.input.height + ctx.input.width),
    )
)

geometry.add_task(
    Task(
        name="area",
        description="Calculate area of a rectangle",
        input=[
            IntInput(name="height", description="Height", default=10),
            IntInput(name="width", description="Width", default=5),
        ],
        action="{ctx.input.height * ctx.input.width}",
    )
)

# =============================================================================
# Task Alias
# =============================================================================

# You can add an alias for easier access
geometry.add_task(
    Task(
        name="square-area",
        description="Calculate area of a square",
        input=[IntInput(name="side", description="Side length", default=5)],
        action=lambda ctx: ctx.input.side**2,
    ),
    # This creates an alias "calculate-area" pointing to this task
    alias="calc-area",
)
