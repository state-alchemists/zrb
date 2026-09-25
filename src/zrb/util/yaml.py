from typing import Any


def yaml_dump(obj: Any, key: str = "") -> str:
    """Rules:
    - Any non-first level multiline string should be rendered as block (using `|`)
    - None values are rendered correctly (not omitted)
    - Non-primitive/list/dict/set objects are ignored
    """
    # lazy: heavy third-party
    import yaml

    processed_obj = _sanitize_obj(obj)
    if key:
        key_parts = _parse_key(key)
        obj_to_dump = get_obj_value(processed_obj, key_parts)
    else:
        obj_to_dump = processed_obj
    yaml.add_representer(str, _multiline_string_presenter)
    yaml_str = yaml.dump(
        obj_to_dump,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        explicit_end=False,
        width=float("inf"),
    )
    # PyYAML appends a '...\n' document-end marker to top-level scalars.
    if not isinstance(obj_to_dump, (dict, list)) and yaml_str.endswith("...\n"):
        yaml_str = yaml_str[:-4]
    return yaml_str


def edit_obj(obj: Any, key: str, val: str) -> Any:
    """`key` nests with '.' as separator; `val` is parsed as YAML before being set.

    Example:
        edit({"a": {"b": 1}}, "a.b", "2") -> {"a": {"b": 2}}
        edit({"flag": False}, "flag", "true") -> {"flag": True}
        edit({"a": 1}, "", "2") -> 2  # Replace entire object with scalar
        edit({"a": 1}, "", "b: 2") -> {"a": 1, "b": 2}  # Patch dict if obj is dict
    """
    parsed_value = load_yaml(val)

    if not key:
        if isinstance(obj, dict) and isinstance(parsed_value, dict):
            return {**obj, **parsed_value}
        return parsed_value

    key_parts = _parse_key(key)
    return set_obj_value(obj, key_parts, parsed_value)


def _sanitize_obj(obj: Any) -> Any:
    """Process a value for YAML conversion."""
    if obj is None or isinstance(obj, (int, float, bool, str)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_sanitize_obj(item) for item in obj if not _is_complex_obj(item)]
    if isinstance(obj, dict):
        return {k: _sanitize_obj(v) for k, v in obj.items() if not _is_complex_obj(v)}
    if isinstance(obj, set):
        return [
            _sanitize_obj(item) for item in sorted(obj) if not _is_complex_obj(item)
        ]
    return None


def _is_complex_obj(obj: Any) -> bool:
    return obj is not None and not isinstance(
        obj, (int, float, bool, str, list, tuple, dict, set)
    )


def _multiline_string_presenter(dumper, data):
    """Custom representer for multiline strings."""
    if "\n" in data:
        lines = [line.rstrip() for line in data.splitlines()]
        clean_data = "\n".join(lines)
        return dumper.represent_scalar("tag:yaml.org,2002:str", clean_data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


def _parse_key(key: str) -> list[str]:
    return key.split(".")


def load_yaml(value_str: str) -> Any:
    """Parse a string value using YAML rules."""
    # lazy: heavy third-party
    import yaml

    if value_str == "":
        return ""
    try:
        return yaml.safe_load(value_str)
    except yaml.YAMLError:
        return value_str


def set_obj_value(obj: Any, keys: list[str], value: Any) -> Any:
    """Set a value in a nested structure."""
    if not keys:
        return value
    current_key = keys[0]
    remaining_keys = keys[1:]
    if isinstance(obj, dict):
        if remaining_keys:
            if current_key not in obj:
                obj[current_key] = {}
            obj[current_key] = set_obj_value(obj[current_key], remaining_keys, value)
        else:
            obj[current_key] = value
        return obj
    if isinstance(obj, list):
        try:
            index = int(current_key)
            if 0 <= index < len(obj):
                if remaining_keys:
                    obj[index] = set_obj_value(obj[index], remaining_keys, value)
                else:
                    obj[index] = value
            else:
                raise IndexError(
                    f"Index {index} out of range for list of length {len(obj)}"
                )
        except ValueError:
            raise KeyError(f"Cannot use non-integer key '{current_key}' with list")
        return obj
    if remaining_keys:
        return {current_key: set_obj_value({}, remaining_keys, value)}
    return {current_key: value}


def get_obj_value(obj: Any, keys: list[str]) -> Any:
    """Get a value from a nested structure; None if the key path does not exist."""
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
