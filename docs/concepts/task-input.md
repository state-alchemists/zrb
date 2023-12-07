🔖 [Table of Contents](../README.md)

# Task Input

<!--start-doc-->
## `Input`

Task Input.

You can use Input to make your Task more interactive.

__Attributes:__

- `name` (`str`): Group name.
- `shortcut` (`Optional[str]`): Input shortcut, single character
- `default` (`Optional[Any]`): Input default value
- `description` (`Optional[str]`): Description of the group.
show_default Union[bool, JinjaTemplate, None]: Whether show default or not.

__Examples:__

```python
from zrb import Input, Task
task = Task(
    name='task',
    inputs=[
        Input(name='delay', default=10, description='Delay')
    ]
)
```


### `Input.get_default`

Getting input default value

### `Input.get_name`

Getting input name

### `Input.get_options`

No documentation available.


### `Input.get_param_decl`

Getting param declaration

### `Input.is_hidden`

No documentation available.


### `Input.should_render`

No documentation available.


<!--end-doc-->

🔖 [Table of Contents](../README.md)
