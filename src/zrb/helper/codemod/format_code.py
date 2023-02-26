import autopep8


def format_code(code: str) -> str:
    return autopep8.fix_code(code)
