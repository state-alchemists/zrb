# Async Task Example

Shows how to create async tasks with `asyncio`.

## Basic Async Task

```python
@make_task(name="sleep")
async def sleep_task(ctx: AnyContext):
    ctx.print("Starting...")
    await asyncio.sleep(1)
    ctx.print("Done!")
    return "slept"
```

## Running

```bash
cd examples/async-task

# Basic async
zrb sleep

# With input
zrb countdown --start 10

# Process items
zrb process --items 20

# Concurrent fetch
zrb fetch-all

# Retry on failure
zrb retry-task

# Mixed sync/async
zrb mixed
```

## Key Patterns

### Async with Input

```python
@make_task(name="countdown", input=[IntInput(name="start")])
async def countdown(ctx: AnyContext):
    for i in range(ctx.input.start, 0, -1):
        ctx.print(f"{i}...")
        await asyncio.sleep(0.5)
```

### Concurrent Operations

```python
@make_task(name="fetch-all")
async def fetch_all(ctx: AnyContext):
    results = await asyncio.gather(*[
        fetch_data(url) for url in urls
    ])
    return results
```

### With Retry

```python
@make_task(name="flaky", retry=3)
async def flaky_task(ctx: AnyContext):
    if random.random() < 0.7:
        raise ValueError("Random failure!")
    return "success"
```

## When to Use Async

| Use Case | Why Async? |
|----------|------------|
| HTTP requests | Don't block while waiting |
| File I/O | Concurrent reads/writes |
| Database queries | Wait on DB responses |
| External APIs | Network latency |

## Key Concepts

| Concept | Description |
|---------|-------------|
| `async def action(ctx)` | Async task function |
| `await asyncio.sleep()` | Simulate delay |
| `await asyncio.gather(*tasks)` | Run concurrently |
| `retry=N` | Retry on failure |
