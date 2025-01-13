import inspect
from collections.abc import Callable
from typing import Annotated, Any, Literal, get_type_hints


def callable_to_tool_schema(callable_obj: Callable) -> dict[str, Any]:
    """
    Convert a callable into a tool schema dictionary by deriving the parameter schema.

    :param callable_obj: The callable object (e.g., a function).
    :return: A dictionary representing the tool schema.
    """
    if not callable(callable_obj):
        raise ValueError("Provided object is not callable")
    # Derive name and description
    name = callable_obj.__name__
    description = (callable_obj.__doc__ or "").strip()
    # Get function signature
    sig = inspect.signature(callable_obj)
    hints = get_type_hints(callable_obj)
    # Build parameter schema
    param_schema = {"type": "object", "properties": {}, "required": []}
    for param_name, param in sig.parameters.items():
        # Get the type hint or default to str
        param_type = hints.get(param_name, str)

        # Handle annotated types (e.g., Annotated[str, "description"])
        json_type, param_metadata = _process_type_annotation(param_type)
        param_schema["properties"][param_name] = param_metadata

        # Mark required parameters
        if param.default is inspect.Parameter.empty:
            param_schema["required"].append(param_name)
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": param_schema,
        },
    }


def _process_type_annotation(py_type: Any) -> tuple[str, dict]:
    """
    Process type annotations and return the JSON Schema type and metadata.

    :param py_type: The type annotation.
    :return: A tuple of (JSON type, parameter metadata).
    """
    if hasattr(py_type, "__origin__") and py_type.__origin__ is Literal:
        # Handle Literal (enum)
        enum_values = list(py_type.__args__)
        return "string", {"type": "string", "enum": enum_values}

    if hasattr(py_type, "__origin__") and py_type.__origin__ is Annotated:
        # Handle Annotated types
        base_type = py_type.__args__[0]
        description = py_type.__args__[1]
        json_type = _python_type_to_json_type(base_type)
        return json_type, {"type": json_type, "description": description}

    # Fallback to basic type conversion
    json_type = _python_type_to_json_type(py_type)
    return json_type, {"type": json_type}


def _python_type_to_json_type(py_type):
    """
    Map Python types to JSON Schema types.
    """
    if py_type is str:
        return "string"
    elif py_type is int:
        return "integer"
    elif py_type is float:
        return "number"
    elif py_type is bool:
        return "boolean"
    elif py_type is list:
        return "array"
    elif py_type is dict:
        return "object"
    elif py_type in {None, type(None)}:
        return "null"
    else:
        return "string"  # Default to string for unsupported types
