import autopep8

from zrb.helper.typecheck import typechecked


@typechecked
def format_code(code: str) -> str:
    return autopep8.fix_code(code)
