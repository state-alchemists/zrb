"""A panel reply still reaches a UI that has no panel.

`BaseUI.show_panel` is the fallback every UI but the default one uses: same
content, printed under its title, instead of a float it does not have.
"""

from zrb.llm.ui.base.ui import BaseUI


class _PrintingUI(BaseUI):
    """A UI that only prints: no float, no panel, nothing to fill."""

    def __init__(self) -> None:
        self.shown: list[str] = []

    def append_to_output(self, *values: object, **kwargs: object) -> None:
        self.shown.append(" ".join(str(value) for value in values))


def test_the_default_panel_prints_the_reply_under_its_title():
    ui = _PrintingUI()

    ui.show_panel("Usage", "  every recorded run")

    assert "Usage" in ui.shown[0]
    assert "every recorded run" in ui.shown[0]
