import sys

from zrb.helper.accessories.color import colored
from zrb.helper.task import show_lines as task_show_lines
from zrb.helper.typecheck import typechecked
from zrb.task.task import Task

_DEPRECATION_WARNING = """
DEPRECATED: zrb.helper.python_task
Use zrb.helper.task instead

```python
from zrb.helper.task import show_lines
```
"""

print(colored(_DEPRECATION_WARNING, color="red", attrs=["bold"]), file=sys.stderr)


@typechecked
def show_lines(task: Task, *lines: str):
    task_show_lines(task, *lines)
