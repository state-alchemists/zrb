🔖 [Table of Contents](../README.md) / [Oops, I Did It Again](README.md)

# Defining Different Tasks With The Same Name Under The Same Group

```python
from zrb import CmdTask, runner

hello1 = CmdTask(
    name='hello',
    group=None,
    cmd='echo "hello mars"'
)
runner.register(hello1)

hello2 = CmdTask(
    name='hello',
    group=None,
    cmd='echo "hello world"'
)
runner.register(hello2)
```

You can see that `hello1` and `hello2` share the same name and group.

The condition leads to a tricky situation since `hello2` overrides `hello1`. To avoid this situation, Zrb will throw a `ValueError` whenever it detects two tasks registered under the same name and group.

# Detecting the Problem

You can detect the problem by reading the error message (i.e., `Task "..." has already been registered`):

```
  ...
  File "/home/gofrendi/playground/getting-started/zrb_init.py", line 14, in <module>
    runner.register(hello2)
  File "<@beartype(zrb.action.runner.Runner.register) at 0x7f780fda8dc0>", line 22, in register
  File "/home/gofrendi/zrb/.venv/lib/python3.10/site-packages/zrb/action/runner.py", line 35, in register
    raise RuntimeError(f'Task "{cmd_name}" has already been registered')
RuntimeError: Task "zrb hello" has already been registered
```

The traceback also shows you that the cause of the error is at line `14` of `zrb_init.py` (i.e., `runner.register(hello2)`).


# Avoiding the Problem

To avoid the problem completely, you can do:

- Always un `zrb` or `zrb [task-groups]` to see list of registered task name.
- Organize your tak definiton location.
    - Put tasks that has similar context under the same `task-group`.
    - Put those tasks physically close to each other (at the same file of under the same directory).


🔖 [Table of Contents](../README.md) / [Oops, I Did It Again](README.md)
