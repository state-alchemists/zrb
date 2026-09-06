🔖 [Documentation Home](../../README.md) > [Core Concepts](./) > XCom Deep Dive

# XCom: Cross-Task Communication

XCom (Cross-Communication) is Zrb's built-in mechanism for passing data between tasks in a pipeline. Every task has its own XCom queue — a `deque`-based FIFO (first-in, first-out) buffer.

---

## Table of Contents

- [How XCom Works](#how-xcom-works)
- [Automatic Data Flow](#automatic-data-flow)
- [Manual XCom Manipulation](#manual-xcom-manipulation)
- [XCom with CmdTask](#xcom-with-cmdtask)
- [XCom in F-String Templates](#xcom-in-f-string-templates)
- [Common Patterns](#common-patterns)
- [Edge Cases & Pitfalls](#edge-cases--pitfalls)

---

## How XCom Works

When a session starts, Zrb creates an `XCom` object containing one `deque` per task. The `XCom` is accessible via `ctx.xcom`:

```python
# Access another task's queue
ctx.xcom["upstream-task-name"]

# Access your own task's queue (use the literal name you gave the task)
ctx.xcom["my-task-name"]
```

> **Note:** There is no public way to read a task's own name back from `ctx` — the task name is stored privately and is not exposed as an attribute. Use the literal string you passed as `name=...` when defining the task.

Each queue supports the following operations:

| Method | Description | Returns |
|--------|-------------|---------|
| `.push(value)` | Add a value to the end of the queue | `None` |
| `.pop()` | Remove and return the oldest item | The value |
| `.popright()` | Remove and return the newest (most recently pushed) item | The value |
| `.peek()` | View the oldest item without removing | The value |
| `.get()` | Read the most recently pushed value without removing; returns `None` if empty | Value or `None` |
| `.set(value)` | Push a value, then discard everything except that latest value | `None` |

---

## Automatic Data Flow

The return value of a task's action function is **automatically pushed** to its XCom queue:

```python
from zrb import make_task, cli

@make_task(name="producer", group=cli)
def produce(ctx):
    return {"status": "ok", "data": [1, 2, 3]}  # Auto-pushed to ctx.xcom["producer"]
```

For `CmdTask`, the action returns a `CmdResult` object (capturing stdout, stderr, and exit code), and that object is pushed as-is:

```python
producer = cli.add_task(CmdTask(name="producer", cmd="echo 'Hello from shell'"))
# ctx.xcom["producer"].pop() returns a CmdResult, not a plain string.
# CmdResult stringifies to the command's stdout, so f"{result}" or str(result)
# gives you "Hello from shell".
```

---

## Manual XCom Manipulation

### Pushing Data

```python
@make_task(name="worker", group=cli)
def work(ctx):
    # Push multiple values
    ctx.xcom["worker"].push("first")
    ctx.xcom["worker"].push("second")
    # Queue now contains: ["first", "second"] (FIFO)
```

### Popping Data

```python
@make_task(name="consumer", upstream=["worker"], group=cli)
def consume(ctx):
    first = ctx.xcom["worker"].pop()    # "first"
    second = ctx.xcom["worker"].pop()   # "second"
    empty = ctx.xcom["worker"].get()    # None (queue is empty)
    # ctx.xcom["worker"].pop() would raise IndexError
```

### Peeking Without Removal

```python
@make_task(name="inspector", upstream=["producer"], group=cli)
def inspect(ctx):
    value = ctx.xcom["producer"].peek()  # View without removing
    ctx.print(f"About to process: {value}")
    actual = ctx.xcom["producer"].pop()   # Now remove it
```

---

## XCom with CmdTask

For `CmdTask`, use f-string-style templating (single `{}`) to access XCom directly in shell commands:

```python
from zrb import cli, CmdTask

producer = cli.add_task(CmdTask(name="producer", cmd="echo 'data-123'"))

consumer = cli.add_task(
    CmdTask(
        name="consumer",
        upstream=[producer],
        cmd="echo 'Processing: {ctx.xcom[\"producer\"].pop()}'",
    )
)
# Output: Processing: data-123
```

> **Note:** When referencing task names with hyphens, use bracket notation with quotes: `{ctx.xcom[\"my-task\"].pop()}`

---

## XCom in F-String Templates

XCom values can be used in any `{ }` expression within task parameters, not just `CmdTask` commands:

```python
from zrb import Scaffolder, StrInput, cli

creator = cli.add_task(CmdTask(name="creator", cmd="echo 'my-app'"))

scaffold = cli.add_task(
    Scaffolder(
        name="scaffold",
        upstream=[creator],
        source_path="./templates/app",
        destination_path="./projects/{ctx.xcom['creator'].peek()}",
        transform_content={
            "APP_NAME": "{ctx.xcom['creator'].pop()}"
        }
    )
)
```

> **Note:** `creator` only pushes one value, but the template reads it twice. Since `.pop()` removes the item, the second read here uses `.peek()` (non-destructive) for `destination_path` and `.pop()` (destructive) for `transform_content`, so both placeholders resolve to the same value without raising `IndexError`.

---

## Common Patterns

### Fan-In: Aggregate Multiple Sources

```python
@make_task(name="aggregator", upstream=[source_a, source_b, source_c], group=cli)
def aggregate(ctx):
    results = [
        ctx.xcom["source_a"].pop(),
        ctx.xcom["source_b"].pop(),
        ctx.xcom["source_c"].pop(),
    ]
    ctx.print(f"Aggregated: {results}")
    return results
```

### Pipeline: Pass Data Through Stages

```python
stage_1 = cli.add_task(CmdTask(name="fetch", cmd="curl https://api.example.com/data"))

@make_task(name="transform", upstream=[stage_1], group=cli)
def transform(ctx):
    raw = ctx.xcom["fetch"].pop()  # a CmdResult, not a plain string
    processed = str(raw).upper()
    return processed  # Pass to next stage

stage_3 = cli.add_task(CmdTask(
    name="save",
    upstream=[transform],
    cmd="echo '{ctx.xcom[\"transform\"].pop()}' > output.txt"
))
```

### Broadcasting: One Producer, Many Consumers

Each consumer calls `.pop()` independently, so you must push multiple copies or use `.peek()` for read-only access:

```python
@make_task(name="broadcaster", group=cli)
def broadcast(ctx):
    value = {"config": "production"}
    ctx.xcom["broadcaster"].push(value)
    ctx.xcom["broadcaster"].push(value)  # Second copy
    return value

# Both consumers will get a value
```

### Using XCom for Manual Trigger Callbacks

XCom is the foundation of trigger-callback patterns:

```python
from zrb import BaseTrigger, Callback

my_callback = Callback(
    task=CmdTask(name="on-event", cmd="echo '{ctx.input.message}'"),
    input_mapping={"message": "{ctx.xcom.event_queue.pop()}"}
)

# Inside the trigger action:
# ctx.xcom.event_queue.push(event_data)
# → pushes to "event_queue" → fires callback → maps to input.message
```

---

## Edge Cases & Pitfalls

| Issue | Behavior | Mitigation |
|-------|----------|------------|
| **Pop from empty queue** | `pop()` raises `IndexError` | Use `.get()` which returns `None` |
| **Reading a task that hasn't run yet** | `ctx.xcom["other"]` raises `KeyError` if that task hasn't executed in this session at all; `.pop()`/`.peek()` raise `IndexError` if the task ran but hasn't pushed a value yet (or the value was already popped) | `ctx.xcom` is one shared, session-wide dict — `upstream` only controls execution *order*, it does not restrict xcom visibility. Make sure the producing task has actually run and pushed before you read from it |
| **Multiple pops** | Each `.pop()` removes one item | Push once per consumer, or use `.peek()` for read-only |
| **Task name with hyphens** | `ctx.xcom.my-task` is invalid Python | Use bracket notation: `ctx.xcom["my-task"]` |
| **Large data** | XCom is in-memory (`deque`) | Not designed for large payloads (>1 MB) |
| **Non-serializable types** | Queues store Python objects | Only works within the same process; cannot persist arbitrary objects |

---

## Quick Reference

```python
# Push
ctx.xcom["task-name"].push(value)

# Pop (raises IndexError if empty)
value = ctx.xcom["task-name"].pop()

# Read latest value (returns None if empty)
value = ctx.xcom["task-name"].get()

# Peek (view without removing)
value = ctx.xcom["task-name"].peek()

# Push to self (use the literal name you gave the task; ctx has no
# public way to read a task's own name back)
ctx.xcom["my-task-name"].push(value)

# Auto-push via return value (inside @make_task function)
def my_task(ctx):
    return value  # Auto-pushed to ctx.xcom["my-task"]

# In CmdTask / f-string templates (escape quotes for hyphens)
# {ctx.xcom["my-task"].pop()}
```

🔖 [Documentation Home](../../README.md) > [Core Concepts](./) > XCom Deep Dive
