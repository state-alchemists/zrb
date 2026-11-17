"""The shell judge's session switch."""

from types import SimpleNamespace


def test_the_session_switch_beats_the_deployment(monkeypatch):
    """A `/judge` in one conversation does not decide what another one judges.

    The switch lives on the session's UI rather than in `CFG` for the reason
    `/sandbox` does: the config belongs to the process and a second chat shares
    it.
    """
    from zrb.config.config import CFG
    from zrb.llm.approval.judge_state import is_shell_judge_enabled_for

    monkeypatch.setattr(CFG, "LLM_SHELL_JUDGE_ENABLED", False)
    session = SimpleNamespace(tools=SimpleNamespace(judge_override=None))
    neighbour = SimpleNamespace(tools=SimpleNamespace(judge_override=None))

    assert is_shell_judge_enabled_for(session) is False

    session.tools.judge_override = True

    assert is_shell_judge_enabled_for(session) is True
    assert is_shell_judge_enabled_for(neighbour) is False
    assert CFG.LLM_SHELL_JUDGE_ENABLED is False


def test_a_deployment_that_judges_is_what_a_silent_session_follows(monkeypatch):
    """No switch of its own means the config decides, in both directions."""
    from zrb.config.config import CFG
    from zrb.llm.approval.judge_state import is_shell_judge_enabled_for

    session = SimpleNamespace(tools=SimpleNamespace(judge_override=None))

    monkeypatch.setattr(CFG, "LLM_SHELL_JUDGE_ENABLED", True)
    assert is_shell_judge_enabled_for(session) is True

    session.tools.judge_override = False
    assert is_shell_judge_enabled_for(session) is False


def test_a_silent_session_follows_the_deployment_on_both_halves(monkeypatch):
    from zrb.config.config import CFG
    from zrb.llm.approval.judge_state import (
        is_shell_judge_auto_approve_enabled_for,
    )

    monkeypatch.setattr(CFG, "LLM_SHELL_JUDGE_ENABLED", True)
    monkeypatch.setattr(CFG, "LLM_SHELL_JUDGE_AUTO_APPROVE_ENABLED", True)
    session = SimpleNamespace(tools=SimpleNamespace(judge_override=None))

    assert is_shell_judge_auto_approve_enabled_for(session) is True

    monkeypatch.setattr(CFG, "LLM_SHELL_JUDGE_AUTO_APPROVE_ENABLED", False)
    assert is_shell_judge_auto_approve_enabled_for(session) is False


def test_a_session_that_asks_to_be_consulted_withdraws_the_auto_half(monkeypatch):
    """`/judge on` says "consult, and still ask". Every keystroke may move the
    judge towards asking; only a launch flag or the environment may hand a
    prompt away."""
    from zrb.config.config import CFG
    from zrb.llm.approval.judge_state import (
        is_shell_judge_auto_approve_enabled_for,
    )

    monkeypatch.setattr(CFG, "LLM_SHELL_JUDGE_AUTO_APPROVE_ENABLED", True)
    session = SimpleNamespace(tools=SimpleNamespace(judge_override=True))

    assert is_shell_judge_auto_approve_enabled_for(session) is False

    session.tools.judge_override = False
    assert is_shell_judge_auto_approve_enabled_for(session) is False
