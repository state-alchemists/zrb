# Basic Task Example

This example shows how to create simple Zrb tasks with inputs and actions.

## Task Types

### Lambda Action

Use a lambda function for simple operations:

```python
Task(
    name="hello",
    input=[StrInput(name="name", default="World")],
    action=lambda ctx: f"Hello, {ctx.input.name}!",
)
```

### String Template Action

Use a string template for text output:

```python
Task(
    name="greet",
    input=[StrInput(name="name", default="Friend")],
    action="Greetings, {ctx.input.name}! Welcome to Zrb.",
)
```

### Function Action (Decorator)

Use `@make_task` for more complex logic:

```python
@make_task(name="multiply", input=[...])
def multiply(ctx):
    result = ctx.input.a * ctx.input.b
    ctx.print("Calculating...")
    return result
```

## Running

```bash
cd examples/basic-task
zrb hello --name "Alice"
zrb greet --name "Bob"
zrb add --a 5 --b 3
zrb multiply --a 4 --b 7
zrb total --price 100 --tax-rate 10
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| `input` | Define task inputs with defaults |
| `action` | Lambda, function, or string template |
| `ctx.input` | Access input values |
| `ctx.print()` | Print to stdout |
| `cli.add_task()` | Register task to CLI |

## Input Types

```python
StrInput("name", default="World")      # String input
IntInput("count", default=1)            # Integer input
FloatInput("price", default=0.0)         # Float input
BoolInput("verbose", default=False)      # Boolean input
```
