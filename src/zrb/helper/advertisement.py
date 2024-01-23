import datetime
import random
import re
import sys

from zrb.helper.accessories.color import colored
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Iterable, Optional


@typechecked
class Advertisement:
    def __init__(self, content: str, time_pattern: str = ".*"):
        self.time_pattern = time_pattern
        self.content = content

    def show(self):
        print(colored(self.content, attrs=["dark"]), file=sys.stderr)


@typechecked
def get_advertisement(
    advertisements: Iterable[Advertisement],
) -> Optional[Advertisement]:
    now = datetime.datetime.now().isoformat()
    candidates = [adv for adv in advertisements if re.match(adv.time_pattern, now)]
    if len(candidates) == 0:
        return None
    return random.choice(candidates)
