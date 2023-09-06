from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Mapping


@typechecked
def parse_replacement(text: str, replacement: Mapping[str, str]):
    new_text = text
    for old, new in replacement.items():
        new_text = new_text.replace(old, new)
    return new_text
