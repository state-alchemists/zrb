"""AnyAgentOutput is a deliberately narrow contract. Keep it narrow.

Raising MAX_MEMBERS means a new kind of thing crosses the tool_call -> ui
boundary. That is a design decision; make it on purpose, in review.
"""

from zrb.llm.ui.any_agent_output import AnyAgentOutput

MAX_MEMBERS = 3


def _members() -> list[str]:
    # `dir()`, not `__protocol_attrs__`: the latter is Python 3.12+ and this
    # project supports 3.11 (see `requires-python` in pyproject.toml).
    return sorted(n for n in dir(AnyAgentOutput) if not n.startswith("_"))


def test_agent_output_stays_narrow():
    members = _members()
    assert len(members) <= MAX_MEMBERS, (
        f"AnyAgentOutput grew to {len(members)} members: {members}. "
        "Adding one couples more of the codebase to the UI layer."
    )


def test_any_ui_satisfies_agent_output():
    from zrb.llm.ui.any_ui import AnyUI

    for name in _members():
        assert hasattr(AnyUI, name), f"AnyUI is missing {name}"
