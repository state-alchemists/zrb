"""
Task Dependencies Example

Shows how to chain tasks with:
- Upstream dependencies (<<)
- Downstream dependencies (>>)
- Fallback tasks
- Successor tasks
"""

import asyncio

from zrb import AnyContext, CmdTask, FloatInput, Task, Xcom, cli, make_task

# =============================================================================
# Upstream Dependencies (<<) - Data Flows From Right to Left
# =============================================================================

# "task_a << task_b" means: task_b runs first, then task_a
# Data from task_b is available in task_a's xcom


async def create_natrium(ctx: AnyContext):
    ctx.print("⚗️ Creating natrium...")
    await asyncio.sleep(0.5)
    ctx.print("✅ Natrium created")
    return "Na"


async def create_chlorine(ctx: AnyContext):
    ctx.print("⚗️ Creating chlorine...")
    await asyncio.sleep(0.5)
    ctx.print("✅ Chlorine created")
    return "Cl"


async def create_salt(ctx: AnyContext):
    # Access upstream results via ctx.xcom
    natrium = ctx.xcom["create-natrium"].pop()
    chlorine = ctx.xcom["create-chlorine"].pop()
    ctx.print(f"🧂 Combining {natrium} + {chlorine}...")
    await asyncio.sleep(0.5)
    ctx.print("✅ Salt created: NaCl")
    return "NaCl"


# Create tasks
task_natrium = cli.add_task(Task(name="create-natrium", action=create_natrium))
task_chlorine = cli.add_task(Task(name="create-chlorine", action=create_chlorine))
task_salt = cli.add_task(Task(name="create-salt", action=create_salt))

# Define dependencies:
# create_natrium >> create_salt (natrium flows into salt)
# create_chlorine >> create_salt (chlorine flows into salt)
assert task_natrium >> task_salt
assert task_chlorine >> task_salt

# Now running "create-salt" will automatically run create-natrium and create-chlorine first

# =============================================================================
# Alternative: Downstream Dependencies (<<)
# =============================================================================

# You can also express the same relationship the other way:
# task_salt << task_natrium means: natrium runs before salt


async def prepare_ingredients(ctx: AnyContext):
    ctx.print("📦 Preparing ingredients...")
    return "ingredients"


async def cook_meal(ctx: AnyContext):
    ingredients = ctx.xcom["prepare-ingredients"].pop()
    ctx.print(f"🍳 Cooking with {ingredients}...")
    return "meal"


task_prepare = cli.add_task(
    Task(name="prepare-ingredients", action=prepare_ingredients)
)
task_cook = cli.add_task(Task(name="cook-meal", action=cook_meal))

# cook depends on prepare (prepare runs first, then cook)
assert task_cook << task_prepare

# =============================================================================
# Fallback Tasks
# =============================================================================

# Fallback runs when the main task fails

from decimal import Decimal


@make_task(
    name="calculate-change",
    description="Calculate change from purchase",
    input=[
        FloatInput(name="price", description="Original price", default=100),
        FloatInput(name="paid", description="Amount paid", default=120),
    ],
    fallback=CmdTask(name="fallback", cmd="echo 'Calculation failed, using fallback'"),
)
def calculate_change(ctx: AnyContext):
    if ctx.input.paid < ctx.input.price:
        raise ValueError(f"Insufficient payment: {ctx.input.paid} < {ctx.input.price}")
    change = ctx.input.paid - ctx.input.price
    ctx.print(f"Change: ${change:.2f}")
    return change


# =============================================================================
# Successor Tasks
# =============================================================================

# Successor runs after the main task completes successfully


@make_task(
    name="process-order",
    description="Process a customer order",
    input=[FloatInput(name="amount", default=50)],
    successor=CmdTask(name="receipt", cmd="echo 'Receipt sent!'"),
)
async def process_order(ctx: AnyContext):
    ctx.print(f"Processing order for ${ctx.input.amount}...")
    await asyncio.sleep(0.5)
    ctx.print(f"✅ Order processed")
    return ctx.input.amount
