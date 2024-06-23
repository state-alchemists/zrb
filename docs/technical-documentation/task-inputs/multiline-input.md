🔖 [Table of Contents](../../README.md) / [Technical Documentation](../README.md) / [Task Inputs](README.md)

# MultilineInput

# Technical Specification

<!--start-doc-->
## `MultilineInput`

A specialized input class for handling string-based inputs in various tasks.

`MultilineInput` extends `BaseInput` to manage string-type inputs, supporting features like
default values, prompts, flags, and other customization options. This class is useful
for tasks requiring textual input, such as names, descriptions, or any other string parameters.

__Arguments:__

- `name` (`str`): The name of the input, used as an identifier.
- `shortcut` (`Optional[str]`): An optional shortcut string for the input.
- `default` (`Optional[Any]`): The default value for the input, expected to be a string if set.
- `callback` (`Optional[Any]`): The default value of the input.
- `description` (`Optional[str]`): A brief description of what the input is for.
- `show_default` (`Union[bool, JinjaTemplate, None]`): Determines the default value to be shown.
- `prompt` (`Union[bool, str]`): A boolean or string to prompt the user for input. If `True`, uses the default prompt.
- `confirmation_prompt` (`Union[bool, str]`): If `True`, the user is asked to confirm the input.
- `prompt_required` (`bool`): If `True`, the prompt for input is mandatory.
- `hide_input` (`bool`): If `True`, hides the input value, typically used for sensitive data.
- `is_flag` (`Optional[bool]`): Indicates if the input is a flag. If `True`, the input accepts boolean flag values.
- `flag_value` (`Optional[Any]`): The value associated with the flag if `is_flag` is `True`.
- `multiple` (`bool`): If `True`, allows multiple string values for the input.
- `count` (`bool`): If `True`, counts the occurrences of the input.
- `allow_from_autoenv` (`bool`): If `True`, enables automatic population of the input from environment variables.
- `hidden` (`bool`): If `True`, keeps the input hidden in help messages or documentation.
- `show_choices` (`bool`): If `True`, shows any restricted choices for the input value.
- `show_envvar` (`bool`): If `True`, displays the associated environment variable, if applicable.
- `nargs` (`int`): The number of arguments that the input can accept.
- `should_render` (`bool`): If `True`, renders the input in the user interface or command-line interface.

__Examples:__

```python
multiline_input = MultilineInput(name='sql', default='select * from tbl', extension='sql', description='SQL')
multiline_input.get_default()
```

```
'user123'
```


### `MultilineInput._get_calculated_show_default`

No documentation available.


### `MultilineInput._get_mark_comment`

No documentation available.


### `MultilineInput._wrapped_callback`

No documentation available.


### `MultilineInput._wrapped_default`

No documentation available.


### `MultilineInput.get_default`

Obtains the default value of the input.

__Returns:__

`Any`: The default value of the input. The type can be any, depending on the input specification.

### `MultilineInput.get_name`

Retrieves the name of the input.

__Returns:__

`str`: The name of the input.

### `MultilineInput.get_options`

Provides a mapping (dictionary) representing the input.

__Returns:__

`Mapping[str, Any]`: A dictionary where keys are option names and values are the corresponding details.

### `MultilineInput.get_param_decl`

Fetches a list of parameter option associated with the input (i.e., `-f` or `--file`).

__Returns:__

`List[str]`: A list containing strings of parameter options.

### `MultilineInput.is_hidden`

Checks whether the input value is meant to be hidden from view or output.

__Returns:__

`bool`: True if the input is hidden, False otherwise.

### `MultilineInput.should_render`

Determines whether or not the input should be rendered.

__Returns:__

`bool`: True if the input should be rendered, False otherwise.

<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Technical Documentation](../README.md) / [Task Inputs](README.md)
