🔖 [Table of Contents](../README.md) / [Tutorials](README.md)

# Running Task Programmatically

Aside from running tasks from the terminal, you can also run tasks programmatically. For example:

```python
from zrb import CmdTask

# Create task
cmd_task = CmdTask(
    name='sample',
    cmd='echo hello'
)

# Create function
function = cmd_task.to_function(env_prefix='')

# Invoke function, and show the result
result = function()
print(result.output)
```

This is useful if you want to run Zrb tasks from inside your application.

🔖 [Table of Contents](../README.md) / [Tutorials](README.md)
