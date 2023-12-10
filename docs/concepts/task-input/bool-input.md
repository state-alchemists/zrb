🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Task Input](README.md)

# BoolInput

# Technical Specification

<!--start-doc-->
## `BoolInput`

A specialized input class for handling boolean values in a task input context.

This class extends `BaseInput` and provides specific functionality for boolean type inputs,
including support for default values, prompts, flags, and various customization options.

__Arguments:__

- `name` (`str`): The name of the input.
- `shortcut` (`Optional[str]`): A shortcut string for the input.
- `default` (`Optional[Any]`): The default value for the input. Should be a boolean if set.
- `description` (`Optional[str]`): A brief description of the input.
- `show_default` (`Union[bool, str, None]`): Option to display the default value. Can be a boolean or string representation.
- `prompt` (`Union[bool, str]`): A boolean or string to prompt the user for input. If `True`, uses the default prompt.
- `confirmation_prompt` (`Union[bool, str]`): If set to `True`, the user is asked to confirm the input.
- `prompt_required` (`bool`): If `True`, the prompt for input is mandatory.
- `hide_input` (`bool`): If `True`, the input is hidden (useful for sensitive information).
- `is_flag` (`Optional[bool]`): Indicates if the input is a flag. If `True`, the input accepts boolean flag values.
- `flag_value` (`Optional[Any]`): The value associated with the flag if `is_flag` is `True`.
- `multiple` (`bool`): If `True`, allows multiple values for the input.
- `count` (`bool`): If `True`, counts the occurrences of the input.
- `allow_from_autoenv` (`bool`): If `True`, allows the input to be automatically populated from the environment.
- `hidden` (`bool`): If `True`, the input is not shown in help messages or documentation.
- `show_choices` (`bool`): If `True`, displays the choices available for the input.
- `show_envvar` (`bool`): Indicates whether to display the environment variable associated with this input.
- `nargs` (`int`): The number of arguments that the input can accept.
- `should_render` (`bool`): If `True`, the input is rendered in the UI or command-line interface.

__Examples:__

```python
bool_input = BoolInput(name='confirm', prompt='Do you agree?', default=False)
bool_input.get_default()
```

```
False
```


### `BoolInput.get_default`

Obtains the default value of the input.

__Returns:__

`Any`: The default value of the input. The type can be any, depending on the input specification.

### `BoolInput.get_name`

Retrieves the name of the input.

__Returns:__

`str`: The name of the input.

### `BoolInput.get_options`

Provides a mapping (dictionary) representing the input.

__Returns:__

`Mapping[str, Any]`: A dictionary where keys are option names and values are the corresponding details.

### `BoolInput.get_param_decl`

Fetches a list of parameter option associated with the input (i.e., `-f` or `--file`).

__Returns:__

`List[str]`: A list containing strings of parameter options.

### `BoolInput.is_hidden`

Checks whether the input value is meant to be hidden from view or output.

__Returns:__

`bool`: True if the input is hidden, False otherwise.

### `BoolInput.should_render`

Determines whether or not the input should be rendered.

__Returns:__

`bool`: True if the input should be rendered, False otherwise.

<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Task Input](README.md)
