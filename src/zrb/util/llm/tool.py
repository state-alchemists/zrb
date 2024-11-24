import inspect
from collections.abc import Callable
from typing import Any, get_type_hints


def callable_to_tool_schema(
    callable_obj: Callable, name: str | None, description: str | None
) -> dict[str, Any]:
    """
    Convert a callable into a tool schema dictionary by deriving the parameter schema.

    :param callable_obj: The callable object (e.g., a function).
    :param name: The name to assign to the function in the schema.
    :param description: A description of the function.
    :return: A dictionary representing the tool schema.
    """
    if not callable(callable_obj):
        raise ValueError("Provided object is not callable")

    name = name or callable_obj.__name__
    description = description or (callable_obj.__doc__ or "").strip()
    # Get function signature
    sig = inspect.signature(callable_obj)
    hints = get_type_hints(callable_obj)
    param_schema = {"type": "object", "properties": {}, "required": []}
    for param_name, param in sig.parameters.items():
        param_type = hints.get(param_name, str)  # Default type is string
        param_schema["properties"][param_name] = {
            "type": _python_type_to_json_type(param_type)
        }
        if param.default is inspect.Parameter.empty:
            param_schema["required"].append(param_name)
        # Add optional descriptions for parameters (if available in annotations)
        if hasattr(param.annotation, "__doc__") and param.annotation.__doc__:
            param_schema["properties"][param_name][
                "description"
            ] = param.annotation.__doc__
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": param_schema,
        },
    }


def _python_type_to_json_type(py_type):
    """
    Map Python types to JSON Schema types.
    """
    if py_type in {str, int, float, bool}:
        return py_type.__name__
    elif py_type is list:
        return "array"
    elif py_type is dict:
        return "object"
    elif py_type is None or py_type is type(None):
        return "null"
    else:
        return "string"  # Default to string for unsupported types
