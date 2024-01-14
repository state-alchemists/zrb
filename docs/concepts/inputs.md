🔖 [Table of Contents](../README.md) / [Concepts](README.md)

# Inputs


<div align="center">
  <img src="../_images/emoji/abcd.png"/>
  <p>
    <sub>
      Input: where your program politely asks, 'What's the magic word?
    </sub>
  </p>
</div>


Like most CLI commands, Zrb also allows you to define input arguments for your Tasks. To add input arguments, you can use `inputs` attributes.

There are some available Inputs you can use:

- BoolInput
- ChoiceInput
- FloatInput
- IntInput
- PasswordInput
- StrInput

Let's see the following example:

```python
from zrb import runner, CmdTask, StrInput

hello = CmdTask(
    name='hello',
    inputs=[
        StrInput(name='your-name', default='World')
    ],
    cmd='echo "Hello, {{ input.your_name }}"'
)
runner.register(hello)
```

In the example, you define an Input named `your-name` with the default value `world`.

You can access the input value by using the Jinja Templating syntax `{{ input.your_name }}`. Notice that when you access the input value using the Jinja Template, the input name has to be written in `snake_case` (i.e., separated with underscore).

As for `@python_task`, you can access input value using `**kwargs` argument. Let's see the following example:

```python
from zrb import runner, python_task, Task, StrInput

@python_task(
    name='hello',
    inputs=[
        StrInput(name='your-name', default='world')
    ],
    runner=runner
)
def hello(*args, **kwargs) -> str:
    your_name = kwargs.get('your_name')
    return f'Hello, {your_name}'
```

There are some parameters you can use to define an `Input`.

- __name__: The name of the Input. By convention, this should be kebab-cased (required).
- __default__: The default value of the Input (optional, default: `None`).
- __should_render__: Whether the Input should be rendered as Jinja Template or not (optional, default: `True`).
- __description__: Description of the Input.
- __prompt__: The prompt text (will be used in interactive mode).

For `ChoiceInput`, you will find another parameter named `choices` to define the options. Let's see the following example:

```python
from zrb import ChoiceInput

color_input = ChoiceInput(name='color', choices=['red', 'green', 'blue'], default='red')
```

# Set Input Values

There are two ways to set a Task's input values:

- By entering the interactive mode.
- By providing the CLI arguments. 

For our previous example, you can enter the interactive mode by typing `zrb hello`. Zrb prompts you to set the value of `your-name` input.

```bash
zrb hello
```

```
Your name [world]:
```

If you press `enter`, Zrb will use the default value (i.e., `world`).

Alternatively, you can also parse the CLI argument as follows:

```bash
zrb hello --your-name "gofrendi"
```

# Turn Off Interactive Mode

You can turn off interactive mode by setting `ZRB_SHOW_PROMPT` to `false`. When you do so, Zrb will use default values unless you pass the CLI arguments.

# Upstream Input

For any Task with upstreams, Zrb automatically parses Upstream Inputs into the current Task.

Let's see the following example:

```python
from zrb import runner, CmdTask, StrInput, BoolInput

hello = CmdTask(
    name='hello',
    inputs=[
        StrInput(name='your-name', default='World')
    ],
    cmd='echo "Hello, {{ input.your_name }}"'
)

task = CmdTask(
    name='task',
    inputs=[
        BoolInput(name='ok', default=True)
    ],
    upstreams=[hello],
    cmd='echo Done'
)
runner.register(task)
```

You can see that `task` has `hello` as it's upstream. When you execute the `task`, Zrb will prompt you to set `your-name` value since `hello` is a `task`'s upstream.


```bash
zrb hello
```

```
Ok [True]:
Your name [world]:
```

# Conflicting Inputs

If you declare multiple inputs with the same name, the latter overrides the previous ones.

As for upstreams, Zrb adds upstream inputs at the end of the current task's inputs. But, the upstream input will not override the current task's input. 

Let's see the following example.


```python
from zrb import runner, CmdTask, StrInput, BoolInput

hello = CmdTask(
    name='hello',
    inputs=[
        StrInput(name='your-name', default='World')
    ],
    cmd='echo "Hello, {{ input.your_name }}"'
)

task = CmdTask(
    name='task',
    inputs=[
        BoolInput(name='ok', default=True),
        StrInput(name='your-name', default='Mercury'),
        StrInput(name='your-name', default='Venus'), # Override Mercury
        StrInput(name='your-name', default='Earth') # Override Venus, not overrided by World
    ],
    upstreams=[hello],
    cmd='echo Done'
)
runner.register(task)
```

You will see that the default value of `your-name` will be `Earth` instead of `Mercury`, `Venus`, or `World`.

For more detailed visualization, please look at the following table:

| Input Name | `show.input[0]` | `task.input[0]` | `task.input[1]` | `task.input[2]` | `task.input[3]` | Final |
|------------|-----------------|-----------------|-----------------|-----------------|-----------------|-------|
| ok         |                 | **True**        |                 |                 |                 | True  |
| your_name  | World           |                 | Mercury         | Venus           | **Earth**       | Earth |

# Limitations and Restricition

You cannot use the following keywords as your input names:

- `_task`
- `_args`

# Next

Next, you can learn about [environments](environments.md).


🔖 [Table of Contents](../README.md) / [Concepts](README.md)
