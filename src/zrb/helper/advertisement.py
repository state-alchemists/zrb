import datetime
import random
import re
import sys
from collections.abc import Iterable
from typing import Optional

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked

logger.debug(colored("Loading zrb.helper.advertisement", attrs=["dark"]))


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
