🔖 [Table of Contents](../../README.md) / [Technical Documentation](../README.md) / [Task Inputs](README.md)

# AnyInput

# Technical Specification

<!--start-doc-->
## `AnyInput`

Abstraction for Zrb Input.

This class acts as a template for creating new Inputs.

To define a new Input type, you should extend this class and implement all its methods.
The easiest way to do so is by extending `Input`

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

`list[str]`: A list containing strings of parameter options.

### `AnyInput.is_hidden`

Checks whether the input value is meant to be hidden from view or output.

__Returns:__

`bool`: True if the input is hidden, False otherwise.

### `AnyInput.should_render`

Determines whether or not the input should be rendered.

__Returns:__

`bool`: True if the input should be rendered, False otherwise.

<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Technical Documentation](../README.md) / [Task Inputs](README.md)
