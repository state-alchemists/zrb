from typing import Any


def yaml_dump(obj: Any, key: str = "") -> str:
    """
    Convert any Python object to a YAML string representation.

    Args:
        obj: Any Python object to convert to YAML

    Returns:
        str: YAML string representation of the object

    Rules:
    - Any non-first level multiline string should be rendered as block (using `|`)
    - None values are rendered correctly (not omitted)
    - Non-primitive/list/dict/set objects are ignored
    """
    import yaml

    # Process the object
    processed_obj = _sanitize_obj(obj)
    if key:
        key_parts = _parse_key(key)
        obj_to_dump = _get_obj_value(processed_obj, key_parts)
    else:
        obj_to_dump = processed_obj
    # Add custom representer for multiline strings
    yaml.add_representer(str, _multiline_string_presenter)
    # Generate YAML
    yaml_str = yaml.dump(
        obj_to_dump,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        explicit_end=False,
        width=float("inf"),
    )
    if not isinstance(obj_to_dump, (dict, list)):
        # PyYAML appends '...\n' (document-end) for top-level scalars.
        # So, we remove it.
        if yaml_str.endswith("...\n"):
            yaml_str = yaml_str[:-4]
    return yaml_str


def edit_obj(obj: Any, key: str, val: str) -> Any:
    """
    Edit a property or subproperty of an object using YAML syntax.

    Args:
        obj: The object to edit
        key: The key to edit, can be nested with '.' as separator
        val: The string value to set, will be parsed as YAML

    Returns:
        Any: The modified object

    Example:
        edit({"a": {"b": 1}}, "a.b", "2") -> {"a": {"b": 2}}
        edit({"flag": False}, "flag", "true") -> {"flag": True}
        edit({"a": 1}, "", "2") -> 2  # Replace entire object with scalar
        edit({"a": 1}, "", "b: 2") -> {"a": 1, "b": 2}  # Patch dict if obj is dict
    """
    # Parse the value using YAML rules
    parsed_value = _load_yaml(val)

    # Handle empty key - replace entire object
    if not key:
        if isinstance(obj, dict) and isinstance(parsed_value, dict):
            # Patch/merge the dict values
            return {**obj, **parsed_value}
        # Replace entire object with parsed value
        return parsed_value

    # Split the key by dots
    key_parts = _parse_key(key)
    # Set the nested value
    return _set_obj_value(obj, key_parts, parsed_value)


def _sanitize_obj(obj: Any) -> Any:
    """Process a value for YAML conversion."""
    if obj is None:
        return None
    elif isinstance(obj, (int, float, bool, str)):
        return obj
    elif isinstance(obj, (list, tuple)):
        return [_sanitize_obj(item) for item in obj if not _is_complex_obj(item)]
    elif isinstance(obj, dict):
        return {k: _sanitize_obj(v) for k, v in obj.items() if not _is_complex_obj(v)}
    elif isinstance(obj, set):
        return [
            _sanitize_obj(item) for item in sorted(obj) if not _is_complex_obj(item)
        ]
    else:
        # Ignore non-primitive/list/dict/set objects
        return None


def _is_complex_obj(obj: Any) -> bool:
    return obj is not None and not isinstance(
        obj, (int, float, bool, str, list, tuple, dict, set)
    )


def _multiline_string_presenter(dumper, data):
    """Custom representer for multiline strings."""
    if "\n" in data:
        # Clean up the string for block style
        lines = [line.rstrip() for line in data.splitlines()]
        clean_data = "\n".join(lines)
        return dumper.represent_scalar("tag:yaml.org,2002:str", clean_data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


def _parse_key(key: str) -> list[str]:
    return key.split(".")


def _load_yaml(value_str: str) -> Any:
    """Parse a string value using YAML rules."""
    import yaml

    # Handle empty string explicitly
    if value_str == "":
        return ""
    try:
        # Use yaml.safe_load to parse the value
        parsed = yaml.safe_load(value_str)
        return parsed
    except yaml.YAMLError:
        # If YAML parsing fails, treat as string
        return value_str


def _set_obj_value(obj: Any, keys: list[str], value: Any) -> Any:
    """Set a value in a nested structure."""
    if not keys:
        return value
    current_key = keys[0]
    remaining_keys = keys[1:]
    if isinstance(obj, dict):
        # Handle dictionary
        if remaining_keys:
            # There are more keys to traverse
            if current_key not in obj:
                obj[current_key] = {}
            obj[current_key] = _set_obj_value(obj[current_key], remaining_keys, value)
        else:
            # This is the final key
            obj[current_key] = value
        return obj
    elif isinstance(obj, list):
        # Handle list - convert key to index
        try:
            index = int(current_key)
            if 0 <= index < len(obj):
                if remaining_keys:
                    obj[index] = _set_obj_value(obj[index], remaining_keys, value)
                else:
                    obj[index] = value
            else:
                raise IndexError(
                    f"Index {index} out of range for list of length {len(obj)}"
                )
        except ValueError:
            raise KeyError(f"Cannot use non-integer key '{current_key}' with list")
        return obj
    else:
        # Handle other types by converting to dict
        if remaining_keys:
            # Create nested structure
            new_obj = {current_key: _set_obj_value({}, remaining_keys, value)}
            return new_obj
        else:
            # Replace the entire object
            return {current_key: value}


def _get_obj_value(obj: Any, keys: list[str]) -> Any:
    """
    Get a value from a nested structure using a list of keys.
    Returns None if the key path does not exist.
    """
    current_val = obj
    for key in keys:
        if isinstance(current_val, dict):
            if key in current_val:
                current_val = current_val[key]
            else:
                return None
        elif isinstance(current_val, list):
            try:
                index = int(key)
                if 0 <= index < len(current_val):
                    current_val = current_val[index]
                else:
                    return None
            except (ValueError, TypeError):
                return None
        else:
            return None
    return current_val
