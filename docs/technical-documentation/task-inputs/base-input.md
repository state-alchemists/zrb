🔖 [Table of Contents](../../README.md) / [Technical Documentation](../README.md) / [Task Inputs](README.md)

# BaseInput

# Technical Specification

<!--start-doc-->
## `BaseInput`

Base class for all Input.

Input is an interface for a Task to read user input at the beginning of the execution.

__Attributes:__

- `name` (`str`): The name of the input, used as a unique identifier.
- `shortcut` (`Optional[str]`): An optional single-character shortcut for the input.
- `default` (`Optional[Any]`): The default value of the input.
- `callback` (`Optional[Any]`): The default value of the input.
- `description` (`Optional[str]`): A brief description of what the input is for.
- `show_default` (`Union[bool, JinjaTemplate, None]`): Determines the default value to be shown.
- `prompt` (`Union[bool, str]`): The prompt text to be displayed when asking for the input.
- `confirmation_prompt` (`Union[bool, str]`): A prompt for confirmation if required.
- `prompt_required` (`bool`): Indicates whether a prompt is required.
- `hide_input` (`bool`): If True, the input value will be hidden (e.g., for passwords).
- `is_flag` (`Optional[bool]`): Specifies whether the input is a flag.
- `flag_value` (`Optional[Any]`): The value to be used if the input is a flag.
- `multiple` (`bool`): Allows multiple values for this input if True.
- `count` (`bool`): If True, counts the occurrences of the input.
- `allow_from_autoenv` (`bool`): If True, allows values to be automatically sourced from the environment.
- `type` (`Optional[Any]`): The expected type of the input value.
- `hidden` (`bool`): If True, the input is hidden and not rendered.
- `show_choices` (`bool`): Indicates whether to show available choices for the input.
- `show_envvar` (`bool`): If True, shows the corresponding environment variable.
- `nargs` (`int`): Number of arguments expected for this input.
- `should_render` (`bool`): Determines whether the input should be rendered.

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


### `BaseInput._get_calculated_show_default`

No documentation available.


### `BaseInput._wrapped_callback`

No documentation available.


### `BaseInput._wrapped_default`

No documentation available.


### `BaseInput.get_default`

Obtains the default value of the input.

__Returns:__

`Any`: The default value of the input. The type can be any, depending on the input specification.

### `BaseInput.get_name`

Retrieves the name of the input.

__Returns:__

`str`: The name of the input.

### `BaseInput.get_options`

Provides a mapping (dictionary) representing the input.

__Returns:__

`Mapping[str, Any]`: A dictionary where keys are option names and values are the corresponding details.

### `BaseInput.get_param_decl`

Fetches a list of parameter option associated with the input (i.e., `-f` or `--file`).

__Returns:__

`list[str]`: A list containing strings of parameter options.

### `BaseInput.is_hidden`

Checks whether the input value is meant to be hidden from view or output.

__Returns:__

`bool`: True if the input is hidden, False otherwise.

### `BaseInput.should_render`

Determines whether or not the input should be rendered.

__Returns:__

`bool`: True if the input should be rendered, False otherwise.

<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Technical Documentation](../README.md) / [Task Inputs](README.md)
