🔖 [Table of Contents](../README.md) / [Oops, I Did It Again](README.md)

# Defining Different Tasks with The Same Name

```python
from zrb import CmdTask, runner

hello1 = CmdTask(
    name='hello',
    cmd='echo "hello mars"'
)
runner.register(hello1)

hello2 = CmdTask(
    name='hello',
    cmd='echo "hello world"'
)
runner.register(hello2)
```

You can see that `hello1` and `hello2` share the same name. Thus, `hello2` will override `hello1`

This leads to so many problems.

For example, you believe that `zrb hello` should yield `hello mars`, yet it keep showing `hello world`.

🔖 [Table of Contents](../README.md) / [Oops, I Did It Again](README.md)
