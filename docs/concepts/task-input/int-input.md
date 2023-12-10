🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Task Input](README.md)

# IntInput

# Technical Specification

<!--start-doc-->
## `IntInput`

A specialized input class for handling integer values in task inputs.

`IntInput` extends `BaseInput` to specifically handle inputs where integer values are required.
It supports various features like default values, prompts, flags, and other customization options,
making it suitable for tasks that require numerical input in the form of integers.

__Arguments:__

- `name` (`str`): The name of the input, serving as an identifier.
- `shortcut` (`Optional[str]`): An optional shortcut for easier reference to the input.
- `default` (`Optional[Any]`): The default value for the input, should be an integer if provided.
- `description` (`Optional[str]`): A brief description of what the input represents or its intended use.
- `show_default` (`Union[bool, str, None]`): Option to show the default value in prompts or documentation.
- `prompt` (`Union[bool, str]`): A boolean or string to determine the prompt for user input. If `True`, uses a default prompt.
- `confirmation_prompt` (`Union[bool, str]`): If `True`, the user will be asked to confirm their input.
- `prompt_required` (`bool`): If `True`, makes the input prompt mandatory.
- `hide_input` (`bool`): If `True`, hides the input value, typically used for sensitive information.
- `is_flag` (`Optional[bool]`): Indicates if the input functions as a flag, taking boolean values.
- `flag_value` (`Optional[Any]`): The value associated with the input when used as a flag.
- `multiple` (`bool`): If `True`, allows entering multiple integer values.
- `count` (`bool`): If `True`, counts the occurrences of the input.
- `allow_from_autoenv` (`bool`): If `True`, enables automatic population of the input from environment variables.
- `hidden` (`bool`): If `True`, keeps the input hidden in help messages or documentation.
- `show_choices` (`bool`): If `True`, shows any restricted choices for the input value.
- `show_envvar` (`bool`): If `True`, displays the associated environment variable, if applicable.
- `nargs` (`int`): The number of arguments that the input can accept.
- `should_render` (`bool`): If `True`, renders the input in the user interface or command-line interface.

__Examples:__

```python
int_input = IntInput(name='age', default=30, description='Enter your age')
int_input.get_default()
```

```
30
```


### `IntInput.get_default`

Obtains the default value of the input.

__Returns:__

`Any`: The default value of the input. The type can be any, depending on the input specification.

### `IntInput.get_name`

Retrieves the name of the input.

__Returns:__

`str`: The name of the input.

### `IntInput.get_options`

Provides a mapping (dictionary) representing the input.

__Returns:__

`Mapping[str, Any]`: A dictionary where keys are option names and values are the corresponding details.

### `IntInput.get_param_decl`

Fetches a list of parameter option associated with the input (i.e., `-f` or `--file`).

__Returns:__

`List[str]`: A list containing strings of parameter options.

### `IntInput.is_hidden`

Checks whether the input value is meant to be hidden from view or output.

__Returns:__

`bool`: True if the input is hidden, False otherwise.

### `IntInput.should_render`

Determines whether or not the input should be rendered.

__Returns:__

`bool`: True if the input should be rendered, False otherwise.

<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Task Input](README.md)
