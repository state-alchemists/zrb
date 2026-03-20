"""
Async Task Example

Shows how to create async tasks with asyncio.
"""

import asyncio

from zrb import AnyContext, IntInput, Task, cli, make_task

# =============================================================================
# Basic Async Task
# =============================================================================


@make_task(name="sleep")
async def sleep_task(ctx: AnyContext):
    """Sleep for a moment and return."""
    ctx.print("Starting sleep...")
    await asyncio.sleep(1)
    ctx.print("Done sleeping!")
    return "slept"


# =============================================================================
# Async Task with Input
# =============================================================================


@make_task(
    name="countdown",
    description="Count down from a number",
    input=[IntInput(name="start", description="Starting number", default=5)],
)
async def countdown(ctx: AnyContext):
    """Count down from start to 0."""
    for i in range(ctx.input.start, 0, -1):
        ctx.print(f"{i}...")
        await asyncio.sleep(0.5)
    ctx.print("🚀 Blast off!")
    return 0


# =============================================================================
# Async Task with Progress
# =============================================================================


@make_task(
    name="process",
    description="Process items with progress",
    input=[IntInput(name="items", description="Number of items", default=10)],
)
async def process_items(ctx: AnyContext):
    """Process items one by one with async delay."""
    results = []
    for i in range(ctx.input.items):
        # Simulate async work
        await asyncio.sleep(0.2)
        results.append(f"item-{i}")
        ctx.print(f"Processed {i + 1}/{ctx.input.items}")

    ctx.print(f"✅ All done! Processed {len(results)} items")
    return results


# =============================================================================
# Multiple Concurrent Operations
# =============================================================================


async def fetch_data(url: str, delay: float) -> str:
    """Simulate fetching data from a URL."""
    await asyncio.sleep(delay)
    return f"Data from {url}"


@make_task(name="fetch-all")
async def fetch_all(ctx: AnyContext):
    """Fetch from multiple URLs concurrently."""
    urls = [
        ("https://api.example.com/users", 0.5),
        ("https://api.example.com/posts", 0.3),
        ("https://api.example.com/comments", 0.4),
    ]

    ctx.print("Fetching from multiple sources...")

    # Run all fetches concurrently
    results = await asyncio.gather(*[fetch_data(url, delay) for url, delay in urls])

    ctx.print(f"Fetched {len(results)} resources")
    return results


# =============================================================================
# Async with Error Handling
# =============================================================================


@make_task(
    name="retry-task",
    description="Task with retry logic",
    retry=3,
)
async def retry_task(ctx: AnyContext):
    """A task that might fail but retries."""
    import random

    ctx.print("Attempting operation...")

    if random.random() < 0.7:  # 70% chance of failure
        raise ValueError("Random failure!")

    ctx.print("Success!")
    return "done"


# =============================================================================
# Combining Sync and Async
# =============================================================================


@make_task(name="mixed")
async def mixed_task(ctx: AnyContext):
    """Mix sync and async operations."""
    # Sync part
    ctx.print("Sync: calculating...")
    result = sum(range(100))

    # Async part
    ctx.print("Async: waiting...")
    await asyncio.sleep(0.5)

    # Sync again
    ctx.print(f"Sync: result is {result}")
    return result
