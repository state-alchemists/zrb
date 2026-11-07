"""The inert default for each UI role, one module per role.

A UI mixes in `UIStateDefaultsMixin` (`zrb.llm.ui.fallback.state_defaults`), which
assembles all five. This package is what those parts are made of: implement a
role for real and your member wins on MRO, leave it out and the default here
reports absence instead of raising.
"""

from zrb.llm.ui.fallback.defaults.display import UIDisplayDefaults
from zrb.llm.ui.fallback.defaults.input import UIInputDefaults
from zrb.llm.ui.fallback.defaults.picker import UIPickerDefaults
from zrb.llm.ui.fallback.defaults.session import UISessionDefaults
from zrb.llm.ui.fallback.defaults.tools import UIToolsDefaults

__all__ = [
    "UIDisplayDefaults",
    "UIInputDefaults",
    "UIPickerDefaults",
    "UISessionDefaults",
    "UIToolsDefaults",
]
