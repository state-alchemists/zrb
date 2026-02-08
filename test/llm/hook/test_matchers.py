import pytest

from zrb.llm.hook.interface import HookContext
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.schema import MatcherConfig
from zrb.llm.hook.types import HookEvent, MatcherOperator


class MockContext:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.fixture
def hook_manager():
    return HookManager(auto_load=False)


def test_evaluate_matchers_equals(hook_manager):
    context = HookContext(event=HookEvent.PRE_TOOL_USE, event_data={"tool": "bash"})

    # Match
    matcher = MatcherConfig(
        field="event_data.tool", operator=MatcherOperator.EQUALS, value="bash"
    )
    assert hook_manager._evaluate_matchers([matcher], context) is True

    # No Match
    matcher = MatcherConfig(
        field="event_data.tool", operator=MatcherOperator.EQUALS, value="python"
    )
    assert hook_manager._evaluate_matchers([matcher], context) is False


def test_evaluate_matchers_not_equals(hook_manager):
    context = HookContext(event=HookEvent.PRE_TOOL_USE, event_data={"tool": "bash"})

    # Match
    matcher = MatcherConfig(
        field="event_data.tool", operator=MatcherOperator.NOT_EQUALS, value="python"
    )
    assert hook_manager._evaluate_matchers([matcher], context) is True

    # No Match
    matcher = MatcherConfig(
        field="event_data.tool", operator=MatcherOperator.NOT_EQUALS, value="bash"
    )
    assert hook_manager._evaluate_matchers([matcher], context) is False


def test_evaluate_matchers_contains(hook_manager):
    context = HookContext(
        event=HookEvent.USER_PROMPT_SUBMIT, event_data=None, prompt="hello world"
    )

    # Match
    matcher = MatcherConfig(
        field="prompt", operator=MatcherOperator.CONTAINS, value="world"
    )
    assert hook_manager._evaluate_matchers([matcher], context) is True

    # No Match
    matcher = MatcherConfig(
        field="prompt", operator=MatcherOperator.CONTAINS, value="mars"
    )
    assert hook_manager._evaluate_matchers([matcher], context) is False


def test_evaluate_matchers_starts_with(hook_manager):
    context = HookContext(
        event=HookEvent.USER_PROMPT_SUBMIT, event_data=None, prompt="hello world"
    )

    # Match
    matcher = MatcherConfig(
        field="prompt", operator=MatcherOperator.STARTS_WITH, value="hello"
    )
    assert hook_manager._evaluate_matchers([matcher], context) is True

    # No Match
    matcher = MatcherConfig(
        field="prompt", operator=MatcherOperator.STARTS_WITH, value="world"
    )
    assert hook_manager._evaluate_matchers([matcher], context) is False


def test_evaluate_matchers_ends_with(hook_manager):
    context = HookContext(
        event=HookEvent.USER_PROMPT_SUBMIT, event_data=None, prompt="hello world"
    )

    # Match
    matcher = MatcherConfig(
        field="prompt", operator=MatcherOperator.ENDS_WITH, value="world"
    )
    assert hook_manager._evaluate_matchers([matcher], context) is True

    # No Match
    matcher = MatcherConfig(
        field="prompt", operator=MatcherOperator.ENDS_WITH, value="hello"
    )
    assert hook_manager._evaluate_matchers([matcher], context) is False


def test_evaluate_matchers_regex(hook_manager):
    context = HookContext(
        event=HookEvent.USER_PROMPT_SUBMIT,
        event_data=None,
        prompt="error: file not found",
    )

    # Match
    matcher = MatcherConfig(
        field="prompt", operator=MatcherOperator.REGEX, value="error: .* not found"
    )
    assert hook_manager._evaluate_matchers([matcher], context) is True

    # No Match
    matcher = MatcherConfig(
        field="prompt", operator=MatcherOperator.REGEX, value="^success"
    )
    assert hook_manager._evaluate_matchers([matcher], context) is False

    # Invalid Regex (should safely return False)
    matcher = MatcherConfig(
        field="prompt", operator=MatcherOperator.REGEX, value="[invalid"
    )
    assert hook_manager._evaluate_matchers([matcher], context) is False


def test_evaluate_matchers_glob(hook_manager):
    context = HookContext(
        event=HookEvent.PRE_TOOL_USE, event_data=None, tool_name="script.py"
    )

    # Match
    matcher = MatcherConfig(
        field="tool_name", operator=MatcherOperator.GLOB, value="*.py"
    )
    assert hook_manager._evaluate_matchers([matcher], context) is True

    # No Match
    matcher = MatcherConfig(
        field="tool_name", operator=MatcherOperator.GLOB, value="*.js"
    )
    assert hook_manager._evaluate_matchers([matcher], context) is False


def test_evaluate_matchers_case_sensitivity(hook_manager):
    context = HookContext(
        event=HookEvent.USER_PROMPT_SUBMIT, event_data=None, prompt="Hello World"
    )

    # Case Insensitive Match
    matcher = MatcherConfig(
        field="prompt",
        operator=MatcherOperator.EQUALS,
        value="hello world",
        case_sensitive=False,
    )
    assert hook_manager._evaluate_matchers([matcher], context) is True

    # Case Sensitive Match Fail
    matcher = MatcherConfig(
        field="prompt",
        operator=MatcherOperator.EQUALS,
        value="hello world",
        case_sensitive=True,
    )
    assert hook_manager._evaluate_matchers([matcher], context) is False


def test_evaluate_matchers_nested_field_missing(hook_manager):
    context = HookContext(event=HookEvent.SESSION_START, event_data={})

    # Field missing
    matcher = MatcherConfig(
        field="event_data.missing_key", operator=MatcherOperator.EQUALS, value="value"
    )
    assert hook_manager._evaluate_matchers([matcher], context) is False


def test_evaluate_matchers_multiple(hook_manager):
    context = HookContext(
        event=HookEvent.PRE_TOOL_USE, event_data=None, tool_name="bash", prompt="rm -rf"
    )

    # All match
    matchers = [
        MatcherConfig(field="tool_name", operator=MatcherOperator.EQUALS, value="bash"),
        MatcherConfig(field="prompt", operator=MatcherOperator.CONTAINS, value="rm"),
    ]
    assert hook_manager._evaluate_matchers(matchers, context) is True

    # One fails
    matchers = [
        MatcherConfig(field="tool_name", operator=MatcherOperator.EQUALS, value="bash"),
        MatcherConfig(
            field="prompt", operator=MatcherOperator.CONTAINS, value="safe_command"
        ),
    ]
    assert hook_manager._evaluate_matchers(matchers, context) is False
