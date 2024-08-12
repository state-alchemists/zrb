import re
from collections.abc import Mapping

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked

logger.debug(colored("Loading zrb.helper.string.parse_replacment", attrs=["dark"]))


@typechecked
def parse_replacement(text: str, replacement: Mapping[str, str]):
    new_text = text
    for old, new in replacement.items():
        if len(new.strip().split("\n")) > 1:
            pattern = "".join(["^([ \\t]+)", re.escape(old)])
            new_replacement = "".join(["\\1", new.replace("\n", "\n\\1")])
            new_text = re.sub(pattern, new_replacement, new_text, flags=re.MULTILINE)
            continue
        new_text = new_text.replace(old, new)
    return new_text
