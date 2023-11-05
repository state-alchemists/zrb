🔖 [Table of Contents](../README.md) / [Oops, I Did It Again](README.md)

# Defining Different Tasks With The Same Name

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

This leads to tricky situation. For example, you believe that `zrb hello` should yield `hello mars`, yet it keep showing `hello world`.

# Detecting the Problem

First of all, detecting the problem will be easier if you use the same convention to define task property:
- Use single quote instead of double quote for string value whenever possible
- Not using space between property name and property value (i.e., `name='hello'`)

Once you do so, you can use `search` feature in your IDE/text editor (e.g., `name='hello'`). Make sure every task name is unique.


🔖 [Table of Contents](../README.md) / [Oops, I Did It Again](README.md)
