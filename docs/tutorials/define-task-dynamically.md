🔖 [Table of Contents](../README.md) / [Tutorials](README.md)

# Define Task Dynamically

Every task definition in Zrb are written in Python.

Thus, you can use looping or any programming tricks to define your tasks.

```python
fruits = {
    'apple': '🍏',
    'orange': '🍊',
    'grapes': '🍇',
}

fruit_upstreams: List[Task] = []
for fruit, emoji in fruits.items():
    show_single_fruit = CmdTask(
        name=f'show-{fruit}',
        description=f'Show {fruit}',
        cmd=f'echo {emoji}',
    )
    runner.register(show_single_fruit)
    fruit_upstreams.append(show_single_fruit)

show_fruits = CmdTask(
    name='show-fruits',
    description='Show fruits',
    upstreams=fruit_upstreams,
    cmd='echo show fruits'
)
runner.register(show_fruits)
```

In this example, you define `show-apple`, `show-orange`, and `show-grapes` based on `fruits` dictionary.
Then you make another task named `show-fruts` that depends on the previosly defined task.

You can try to run the tasks:

```bash
zrb show-fruits

# or run the generated task individually:
zrb show-apple
zrb show-orange
zrb show-grapes
```

It should run all previous tasks as well.

🔖 [Table of Contents](../README.md) / [Tutorials](README.md)

