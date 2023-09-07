from zrb.helper.typecheck import typechecked
import autopep8


@typechecked
def format_code(code: str) -> str:
    return autopep8.fix_code(code)
