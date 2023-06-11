🔖 [Table of Contents](../README.md) / [Tutorials](README.md)

# Running task programmatically

Aside from running tasks from the terminal, you can also run tasks programmatically. For example:

```python
from zrb import CmdTask

# Create task
cmd_task = CmdTask(
    name='sample',
    cmd='echo hello'
)

# Create main loop
main_loop = cmd_task.create_main_loop(env_prefix='')

# Invoke main loop, and show the result
result = main_loop()
print(result.output)
```

This is useful if you want to run Zrb tasks from inside your application.

🔖 [Table of Contents](../README.md) / [Tutorials](README.md)
