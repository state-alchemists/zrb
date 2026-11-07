"""One conversation across several interfaces.

`MultiUI` broadcasts output to every child, takes the first answer, and runs a
single turn for all of them. The rest of this package holds its parts; the
names below are the public surface, unchanged from the module this replaced.
"""

from zrb.llm.ui.fallback.resolution import (
    create_combined_ui,
    get_main_ui,
    resolve_ui,
)

from zrb.llm.ui.multi.multi_ui import MultiUI

__all__ = [
    "MultiUI",
    "create_combined_ui",
    "get_main_ui",
    "resolve_ui",
]
