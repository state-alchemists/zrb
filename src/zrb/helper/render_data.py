import datetime
import os
import platform
import time

from zrb.helper.util import (
    coalesce,
    coalesce_str,
    to_boolean,
    to_camel_case,
    to_human_readable,
    to_kebab_case,
    to_pascal_case,
    to_snake_case,
)

DEFAULT_RENDER_DATA = {
    "datetime": datetime,
    "os": os,
    "platform": platform,
    "time": time,
    "util": {
        "coalesce": coalesce,
        "coalesce_str": coalesce_str,
        "to_camel_case": to_camel_case,
        "to_pascal_case": to_pascal_case,
        "to_kebab_case": to_kebab_case,
        "to_snake_case": to_snake_case,
        "to_human_readable": to_human_readable,
        "to_boolean": to_boolean,
    },
}
