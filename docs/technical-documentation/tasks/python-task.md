🔖 [Table of Contents](../../README.md) / [Technical Documentation](../README.md) / [Tasks](README.md)

# `@python_task` Decorator

# Technical Specification

<!--start-doc-->
## `python_task`

python_task decorator helps you turn any Python function into a task

__Returns:__

`Callable[[Callable[..., Any]], Task]`: A callable turning function into task.

__Examples:__

```python
from zrb import python_task
@python_task(
   name='my-task'
)
def my_task(*args, **kwargs):
   return 'hello world'
print(my_task)
```

```
<Task name=my-task>
```


<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Technical Documentation](../README.md) / [Tasks](README.md)
