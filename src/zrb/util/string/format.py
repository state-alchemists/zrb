from typing import Any


def fstring_format(template: str, data: dict[str, Any]) -> str:
    # Safely evaluate the template as a Python expression
    try:
        return eval(f'f"""{template}"""', {}, data)
    except Exception as e:
        raise ValueError(f"Failed to parse template: {template}: {e}")
