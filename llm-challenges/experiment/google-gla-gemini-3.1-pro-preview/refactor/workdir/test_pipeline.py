import re
from typing import List, Dict

def test_regex():
    LOG_PATTERN = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<level>[A-Z]+)\s+(?P<message>.*)$")
    line1 = "2024-01-01 12:00:00 INFO User 42 logged in\n"
    m = LOG_PATTERN.match(line1)
    print(m.groupdict())

    line2 = "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n"
    m2 = LOG_PATTERN.match(line2)
    print(m2.groupdict())

test_regex()
