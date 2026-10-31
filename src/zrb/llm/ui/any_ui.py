"""Compatibility path for the `AnyUI` contract.

`AnyUI` moved to `zrb.llm.any_ui` so an L0 module can name it without loading
this package's `__init__`. Import the new path in new code.
"""

from zrb.llm.any_ui import AnyUI, ChoiceOption, ChoiceSpec

__all__ = ["AnyUI", "ChoiceOption", "ChoiceSpec"]
