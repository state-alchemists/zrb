# Task Dependencies Example

Shows how to chain tasks together.

## Dependency Operators

| Operator | Meaning | Direction |
|----------|---------|-----------|
| `>>` | upstream | `A >> B` = B depends on A |
| `<<` | downstream | `A << B` = A depends on B |

## Data Flow

Upstream task results are available via `ctx.xcom`:

```python
# upstream task
async def create_data(ctx):
    return "result"  # stored in xcom

# downstream task
async def use_data(ctx):
    data = ctx.xcom["create-data"].pop()  # retrieve result
    return process(data)

# define dependency
assert create_task >> use_task  # create runs before use
```

## Running

```bash
cd examples/task-dependencies

# Runs create-natrium and create-chlorine first, then create-salt
zrb create-salt

# Runs prepare-ingredients first, then cook-meal
zrb cook-meal

# Fallback example (fails if paid < price)
zrb calculate-change --price 100 --paid 80

# Successor example (runs receipt after processing)
zrb process-order --amount 50
```

## Fallback vs Successor

```
┌──────────┐
│   Task   │
└────┬─────┘
     │
     ├── FAIL ──► Fallback task runs
     │
     └── SUCCESS ──► Successor task runs
```

- **Fallback**: Runs when main task fails
- **Successor**: Runs when main task succeeds

## Multiple Dependencies

```python
# Salt depends on both natrium AND chlorine
create_natrium >> create_salt
create_chlorine >> create_salt

# Both upstream tasks run in parallel by default
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| `task_a >> task_b` | task_b depends on task_a |
| `task_a << task_b` | task_a depends on task_b |
| `ctx.xcom["task_name"]` | Access upstream results |
| `.pop()` | Get last result from xcom |
| `fallback=` | Task to run on failure |
| `successor=` | Task to run on success |
