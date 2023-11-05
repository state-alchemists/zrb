🔖 [Table of Contents](../README.md) / [Tutorials](README.md)

# Getting Data from Other Tasks 

Zrb doesn't have provide any opinionated solution for communication between task.

However, Zrb will generate an execution id for a single session. You can access the execution id by either using `_ZRB_EXECUTION_ID` or `task.get_execution_id()`:

- For `CmdTask`, you can use `_ZRB_EXECUTION_ID` environment
- For `python_tsak`, you can invoke
    - `task = kwargs.get('_task')` to get the task instance
    - `task.get_execution_id()` to get the execution id.

# Example: Poem

Let's say you have 3 tasks to show a poem:
- `first_part` generate the first half task of the poem
- `second_part` generate the second half task of the poem
- `poem` show the poem to the user.

To do so, you can use `execution id` to create a file that will be manipulated by the tasks.

```python
from typing import Any
from zrb import CmdTask, python_task, AnyTask, runner

first_part = CmdTask(
    name='first_part',
    cmd=[
        'echo "Writing the fist part"',
        'echo "Roses are red" >> "/tmp/$_ZRB_EXECUTION_ID"'
        'echo "\nViolets are blue" >> "/tmp/$_ZRB_EXECUTION_ID"'
    ]
)


@python_task(
    name='second-part',
    upstreams=[first_part]
)
def second_part(*args: Any, **kwargs: Any):
    task: AnyTask = kwargs.get('_task')
    task.print_out('Writing the second part')
    execution_id = task.get_execution_id()
    file_name = f'/tmp/{execution_id}'
    with open(file_name, 'a') as f:
        f.write('It is hot here\n')
        f.write('Or it is just you\n')


poem = CmdTask(
    name='poem',
    upstreams=[second_part],
    cmd='cat "/tmp/$_ZRB_EXECUTION_ID"'
)
runner.register(poem)
```

You can then run the tasks by invoking

```
zrb poem
```

🔖 [Table of Contents](../README.md) / [Tutorials](README.md)
