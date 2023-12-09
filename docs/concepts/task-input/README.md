🔖 [Table of Contents](../../README.md) / [Concepts](../README.md)

# Task Input

Sometimes, you need some user inputs to run your Tasks.

Zrb allows you to set `inputs` for your Task; either by:

- Using `inputs` parameter.
- Using `add_input` method.
- Using `insert_input` method.

All Task Input should comply with `AnyInput` interface.

Currently, there are some built-in inputs you can use:

- [Input](./input.md)
- [BoolInput](./bool-input.md)
- [ChoiceInput](./choice-input.md)
- [FloatInput](./float-input.md)
- [IntInput](./int-input.md)
- [PasswordInput](./password-input.md)
- [StrInput](./str-input.md)

Here, you will see the technical specification of `AnyInput`

# Technical Specification

<!--start-doc-->
## `AnyInput`

Abstract base class representing a generalized input specification.
This class serves as a template for creating various input types,
providing a standardized interface for input handling and processing.

### `AnyInput.get_default`

Obtains the default value of the input.

__Returns:__

`Any`: The default value of the input. The type can be any, depending on the input specification.

### `AnyInput.get_name`

Retrieves the name of the input.

__Returns:__

`str`: The name of the input.

### `AnyInput.get_options`

Provides a mapping (dictionary) representing the input.

__Returns:__

`Mapping[str, Any]`: A dictionary where keys are option names and values are the corresponding details.

### `AnyInput.get_param_decl`

Fetches a list of parameter option associated with the input (i.e., `-f` or `--file`).

__Returns:__

`List[str]`: A list containing strings of parameter options.

### `AnyInput.is_hidden`

Checks whether the input value is meant to be hidden from view or output.

__Returns:__

`bool`: True if the input is hidden, False otherwise.

### `AnyInput.should_render`

Determines whether or not the input should be rendered.

__Returns:__

`bool`: True if the input should be rendered, False otherwise.

<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md)
