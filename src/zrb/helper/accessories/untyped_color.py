from termcolor import colored as term_colored


def untyped_colored(
    text,
    color=None,
    on_color=None,
    attrs=None,
) -> str:
    return term_colored(text, color, on_color, attrs)
