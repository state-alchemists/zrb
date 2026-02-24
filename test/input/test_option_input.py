from unittest.mock import MagicMock, patch

from zrb.context.shared_context import SharedContext
from zrb.input.option_input import OptionInput


def test_option_input_initialization():
    """Test that OptionInput can be instantiated with basic parameters."""
    option_input = OptionInput(
        name="test_option",
        description="Test option description",
        prompt="Choose an option",
        options=["option1", "option2", "option3"],
        default="option2",
        auto_render=True,
        allow_empty=False,
        allow_positional_parsing=True,
        always_prompt=True,
    )

    assert option_input.name == "test_option"
    assert option_input.description == "Test option description"
    assert option_input.prompt_message == "Choose an option"
    assert option_input.always_prompt is True


def test_option_input_to_html():
    """Test HTML generation for option input."""
    option_input = OptionInput(
        name="color",
        description="Choose a color",
        options=["red", "green", "blue"],
        default="green",
    )

    shared_ctx = SharedContext(env={})
    html = option_input.to_html(shared_ctx)

    # Check basic structure
    assert '<select name="color"' in html
    assert 'placeholder="Choose a color"' in html

    # Check options
    assert '<option value="red"' in html
    assert '<option value="green"' in html
    assert '<option value="blue"' in html

    # Check default selection
    assert 'value="green" selected' in html or 'selected" value="green"' in html
    # red and blue should not be selected
    assert 'value="red" selected' not in html
    assert 'value="blue" selected' not in html


def test_option_input_to_html_without_default():
    """Test HTML generation when no default is specified."""
    option_input = OptionInput(
        name="color",
        description="Choose a color",
        options=["red", "green", "blue"],
        default="",  # Empty default
    )

    shared_ctx = SharedContext(env={})
    html = option_input.to_html(shared_ctx)

    # No option should be selected
    assert "selected" not in html or 'selected=""' in html


def test_option_input_get_default_str():
    """Test getting default value as string."""
    option_input = OptionInput(
        name="test",
        options=["a", "b", "c"],
        default="b",
    )

    shared_ctx = SharedContext(env={})
    default_str = option_input.get_default_str(shared_ctx)

    assert default_str == "b"


def test_option_input_get_default_str_empty():
    """Test getting default value when default is empty."""
    option_input = OptionInput(
        name="test",
        options=["a", "b", "c"],
        default="",  # Empty default
    )

    shared_ctx = SharedContext(env={})
    default_str = option_input.get_default_str(shared_ctx)

    assert default_str == ""


def test_option_input_update_shared_context():
    """Test updating shared context with option value."""
    option_input = OptionInput(
        name="choice",
        options=["yes", "no", "maybe"],
        default="yes",
    )

    shared_ctx = SharedContext()

    # Update with valid option
    option_input.update_shared_context(shared_ctx, str_value="no")

    # Check value was set
    assert shared_ctx.input.choice == "no"


def test_option_input_update_shared_context_with_default():
    """Test updating shared context with empty value."""
    option_input = OptionInput(
        name="choice",
        options=["yes", "no", "maybe"],
        default="maybe",
    )

    shared_ctx = SharedContext()

    # Update with empty value - should store empty string (not use default)
    option_input.update_shared_context(shared_ctx, str_value="")

    # Empty string should be stored (default is only used when str_value is None)
    assert shared_ctx.input.choice == ""


# Note: We're not testing _prompt_cli_str, _get_value_from_user_input, or _get_option_completer
# as they are private methods. The public API is already tested through
# update_shared_context, to_html, and get_default_str.


# Note: Private methods like _get_option_completer, _prompt_cli_str validation,
# and prompt flow are not tested as they are implementation details.
# The public API coverage is sufficient.
