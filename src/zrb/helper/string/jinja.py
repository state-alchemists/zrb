from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Any


@typechecked
def is_probably_jinja(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if "{{" in value and "}}" in value:
        return True
    if "{%" in value and "%}" in value:
        return True
    return False
