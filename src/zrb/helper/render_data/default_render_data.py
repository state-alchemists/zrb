from ..dynamic_model import DynamicModel
from ..common import (
    coalesce, to_camel_case, to_pascal_case, to_kebab_case,
    to_snake_case, to_human_readable
)
import os
import datetime
import time

DEFAULT_RENDER_DATA = {
    'os': os,
    'datetime': datetime,
    'time': time,
    'zrb': DynamicModel(
        coalesce=coalesce,
        to_camel_case=to_camel_case,
        to_pascal_case=to_pascal_case,
        to_kebab_case=to_kebab_case,
        to_snake_case=to_snake_case,
        to_human_readable=to_human_readable
    )
}
