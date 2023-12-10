🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Task Input](README.md)

# PasswordInput

# Technical Specification

<!--start-doc-->
## `PasswordInput`

A specialized input class for handling password or sensitive data inputs in tasks.

`PasswordInput` extends `BaseInput` to manage inputs that should be treated as sensitive,
such as passwords. It ensures that the input is hidden when entered, providing an added
layer of security and privacy. This class supports various features like default values,
prompts, and flags, tailored for the safe handling of sensitive information.

__Arguments:__

- `name` (`str`): The name of the input, serving as an identifier.
- `shortcut` (`Optional[str]`): An optional shortcut string for the input.
- `default` (`Optional[Any]`): The default value for the input, expected to be a string if set.
- `description` (`Optional[str]`): A brief description of the input's purpose.
- `show_default` (`Union[bool, str, None]`): Option to display the default value. Can be a boolean or string.
- `prompt` (`Union[bool, str]`): A boolean or string to prompt the user for input. If `True`, uses the default prompt.
- `confirmation_prompt` (`Union[bool, str]`): If `True`, the user is asked to confirm the input.
- `prompt_required` (`bool`): If `True`, the prompt for input is mandatory.
- `is_flag` (`Optional[bool]`): Indicates if the input is a flag. If `True`, the input accepts boolean flag values.
- `flag_value` (`Optional[Any]`): The value associated with the flag if `is_flag` is `True`.
- `multiple` (`bool`): If `True`, allows multiple values for the input.
- `count` (`bool`): If `True`, counts the occurrences of the input.
- `allow_from_autoenv` (`bool`): If `True`, allows the input to be automatically populated from the environment.
- `hidden` (`bool`): If `True`, the input is not shown in help messages or documentation.
- `show_choices` (`bool`): If `True`, displays the available choices to the user (if applicable).
- `show_envvar` (`bool`): Indicates whether to display the environment variable associated with this input.
- `nargs` (`int`): The number of arguments that the input can accept.
- `should_render` (`bool`): If `True’, the input is rendered in the UI or command-line interface.

__Examples:__

```python
password_input = PasswordInput(name='password', description='Enter your password')
password_input.is_hidden()
```

```
True
```


### `PasswordInput.get_default`

Obtains the default value of the input.

__Returns:__

`Any`: The default value of the input. The type can be any, depending on the input specification.

### `PasswordInput.get_name`

Retrieves the name of the input.

__Returns:__

`str`: The name of the input.

### `PasswordInput.get_options`

Provides a mapping (dictionary) representing the input.

__Returns:__

`Mapping[str, Any]`: A dictionary where keys are option names and values are the corresponding details.

### `PasswordInput.get_param_decl`

Fetches a list of parameter option associated with the input (i.e., `-f` or `--file`).

__Returns:__

`List[str]`: A list containing strings of parameter options.

### `PasswordInput.is_hidden`

Checks whether the input value is meant to be hidden from view or output.

__Returns:__

`bool`: True if the input is hidden, False otherwise.

### `PasswordInput.should_render`

Determines whether or not the input should be rendered.

__Returns:__

`bool`: True if the input should be rendered, False otherwise.

<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Task Input](README.md)
