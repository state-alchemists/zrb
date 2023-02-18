from typing import Iterable, Optional
from typeguard import typechecked
from .accessories.color import colored

import datetime
import random
import re
import sys


@typechecked
class Advertisement():
    def __init__(self, content: str, time_pattern: str = '.*'):
        self.time_pattern = time_pattern
        self.content = content

    def show(self):
        print(colored(self.content, attrs=['dark']), file=sys.stderr)


def get_advertisement(
    advertisements: Iterable[Advertisement]
) -> Optional[Advertisement]:
    now = datetime.datetime.now().isoformat()
    candidates = [
        adv
        for adv in advertisements
        if re.match(adv.time_pattern, now)
    ]
    if len(candidates) == 0:
        return None
    return random.choice(candidates)
