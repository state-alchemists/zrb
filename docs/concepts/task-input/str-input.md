🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Task Input](README.md)

# StrInput

# Technical Specification

<!--start-doc-->
## `StrInput`

A specialized input class for handling string-based inputs in various tasks.

`StrInput` extends `BaseInput` to manage string-type inputs, supporting features like
default values, prompts, flags, and other customization options. This class is useful
for tasks requiring textual input, such as names, descriptions, or any other string parameters.

__Arguments:__

- `name` (`str`): The name of the input, used as an identifier.
- `shortcut` (`Optional[str]`): An optional shortcut string for the input.
- `default` (`Optional[Any]`): The default value for the input, expected to be a string if set.
- `description` (`Optional[str]`): A brief description of the input's purpose.
- `show_default` (`Union[bool, str, None]`): Option to display the default value. Can be a boolean or string.
- `prompt` (`Union[bool, str]`): A boolean or string to prompt the user for input. If `True`, uses the default prompt.
- `confirmation_prompt` (`Union[bool, str]`): If `True`, the user is asked to confirm the input.
- `prompt_required` (`bool`): If `True’, the prompt for input is mandatory.
- `hide_input` (`bool`): If `True’, hides the input value, typically used for sensitive data.
- `is_flag` (`Optional[bool]`): Indicates if the input is a flag. If `True’, the input accepts boolean flag values.
- `flag_value` (`Optional[Any]`): The value associated with the flag if `is_flag` is `True`.
- `multiple` (`bool`): If `True’, allows multiple string values for the input.
- `count` (`bool`): If `True’, counts the occurrences of the input.
- `allow_from_autoenv` (`bool`): If `True’, enables automatic population of the input from environment variables.
- `hidden` (`bool`): If `True’, keeps the input hidden in help messages or documentation.
- `show_choices` (`bool`): If `True’, shows any restricted choices for the input value.
- `show_envvar` (`bool`): If `True’, displays the associated environment variable, if applicable.
- `nargs` (`int`): The number of arguments that the input can accept.
- `should_render` (`bool`): If `True’, renders the input in the user interface or command-line interface.

__Examples:__

```python
str_input = StrInput(name='username', default='user123', description='Enter your username')
str_input.get_default()
```

```
'user123'
```


### `StrInput.get_default`

Obtains the default value of the input.

__Returns:__

`Any`: The default value of the input. The type can be any, depending on the input specification.

### `StrInput.get_name`

Retrieves the name of the input.

__Returns:__

`str`: The name of the input.

### `StrInput.get_options`

Provides a mapping (dictionary) representing the input.

__Returns:__

`Mapping[str, Any]`: A dictionary where keys are option names and values are the corresponding details.

### `StrInput.get_param_decl`

Fetches a list of parameter option associated with the input (i.e., `-f` or `--file`).

__Returns:__

`List[str]`: A list containing strings of parameter options.

### `StrInput.is_hidden`

Checks whether the input value is meant to be hidden from view or output.

__Returns:__

`bool`: True if the input is hidden, False otherwise.

### `StrInput.should_render`

Determines whether or not the input should be rendered.

__Returns:__

`bool`: True if the input should be rendered, False otherwise.

<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Task Input](README.md)
