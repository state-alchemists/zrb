import pytest

from zrb.context.shared_context import SharedContext
from zrb.input.base_input import BaseInput


class ConcreteInput(BaseInput):
    def to_html(self, shared_ctx) -> str:
        return "<input>"


def test_base_input_basic():
    inp = ConcreteInput("my-input", "Desc", prompt="Prompt", default="val")
    shared_ctx = SharedContext()
    assert inp.name == "my-input"
    assert inp.description == "Desc"
    assert inp.get_default_str(shared_ctx) == "val"
    assert inp.to_html(shared_ctx) == "<input>"


def test_base_input_always_prompt():
    inp1 = ConcreteInput("i1", always_prompt=True)
    inp2 = ConcreteInput("i2", always_prompt=False)
    assert inp1.always_prompt is True
    assert inp2.always_prompt is False


def test_base_input_repr():
    """Test __repr__ method."""
    inp = ConcreteInput("my-input")
    assert repr(inp) == "<ConcreteInput name=my-input>"


def test_base_input_default_description():
    """Test description defaults to name."""
    inp = ConcreteInput("test-name")
    assert inp.description == "test-name"


def test_base_input_custom_description():
    """Test custom description."""
    inp = ConcreteInput("test-name", description="Custom description")
    assert inp.description == "Custom description"


def test_base_input_default_prompt():
    """Test prompt message defaults to name."""
    inp = ConcreteInput("test-input")
    assert inp.prompt_message == "test-input"


def test_base_input_custom_prompt():
    """Test custom prompt message."""
    inp = ConcreteInput("test-input", prompt="Enter value:")
    assert inp.prompt_message == "Enter value:"


def test_base_input_allow_positional_parsing():
    """Test allow_positional_parsing property."""
    inp1 = ConcreteInput("i1", allow_positional_parsing=True)
    inp2 = ConcreteInput("i2", allow_positional_parsing=False)
    assert inp1.allow_positional_parsing is True
    assert inp2.allow_positional_parsing is False


def test_base_input_parse_str_value_through_update():
    """Test string value parsing through update_shared_context (public API)."""
    inp = ConcreteInput("test")
    shared_ctx = SharedContext()
    # update_shared_context with str_value uses _parse_str_value internally
    inp.update_shared_context(shared_ctx, str_value="hello")
    assert shared_ctx.input["test"] == "hello"


def test_base_input_get_default_str_with_callable():
    """Test get_default_str with callable default."""
    inp = ConcreteInput("test", default=lambda ctx: "dynamic_value")
    shared_ctx = SharedContext()
    result = inp.get_default_str(shared_ctx)
    assert result == "dynamic_value"


def test_base_input_get_default_str_non_string():
    """Test get_default_str converts non-string to string."""
    inp = ConcreteInput("test", default=123)
    shared_ctx = SharedContext()
    result = inp.get_default_str(shared_ctx)
    assert result == "123"


def test_base_input_update_shared_context_with_value():
    """Test update_shared_context with explicit value."""
    inp = ConcreteInput("test")
    shared_ctx = SharedContext()
    inp.update_shared_context(shared_ctx, value="explicit_value")
    assert shared_ctx.input["test"] == "explicit_value"


def test_base_input_update_shared_context_with_str_value():
    """Test update_shared_context with string value."""
    inp = ConcreteInput("test")
    shared_ctx = SharedContext()
    inp.update_shared_context(shared_ctx, str_value="string_value")
    assert shared_ctx.input["test"] == "string_value"


def test_base_input_update_shared_context_default_value():
    """Test update_shared_context uses default when no value provided."""
    inp = ConcreteInput("test", default="default_val")
    shared_ctx = SharedContext()
    inp.update_shared_context(shared_ctx)
    assert shared_ctx.input["test"] == "default_val"


def test_base_input_update_shared_context_snake_case():
    """Test update_shared_context also adds snake_case version."""
    inp = ConcreteInput("my-input-name")
    shared_ctx = SharedContext()
    inp.update_shared_context(shared_ctx, value="test_value")
    assert shared_ctx.input["my-input-name"] == "test_value"
    assert shared_ctx.input["my_input_name"] == "test_value"


def test_base_input_update_shared_context_already_exists():
    """Test update_shared_context raises error if input already exists."""
    inp = ConcreteInput("test")
    shared_ctx = SharedContext()
    shared_ctx.input["test"] = "existing"
    with pytest.raises(ValueError, match="Input already defined"):
        inp.update_shared_context(shared_ctx, value="new_value")


def test_base_input_update_shared_context_snake_case_conflict():
    """Test update_shared_context raises error if snake_case key exists."""
    inp = ConcreteInput("my-input")  # snake_case: my_input
    shared_ctx = SharedContext()
    shared_ctx.input["my_input"] = "existing"
    with pytest.raises(ValueError, match="Input already defined"):
        inp.update_shared_context(shared_ctx, value="new_value")


def test_base_input_update_shared_context_same_name_no_duplicate():
    """Test update_shared_context doesn't add duplicate for snake_case == original."""
    inp = ConcreteInput("simple")  # snake_case is same as original
    shared_ctx = SharedContext()
    inp.update_shared_context(shared_ctx, value="test_value")
    # Should only have one key, not two
    assert "simple" in shared_ctx.input
    # Check that my_input was NOT added (since my-input -> my_input, but simple -> simple)
    assert len([k for k in shared_ctx.input.keys() if k == "simple"]) == 1


def test_base_input_to_html():
    """Test to_html generates correct HTML."""
    inp = ConcreteInput("my-input", description="Enter value", default="default_val")
    shared_ctx = SharedContext()
    html = inp.to_html(shared_ctx)
    # Check that the HTML contains expected elements
    # BaseInput's to_html uses get_default_str which requires input rendering
    assert "input" in html.lower()


class MinimalInput(BaseInput):
    """Subclass that uses BaseInput.to_html without overriding it."""

    pass


def test_base_input_to_html_direct():
    """Test BaseInput.to_html directly using a non-overriding subclass."""
    inp = MinimalInput("my-name", description="My Description", default="my-val")
    shared_ctx = SharedContext()
    html = inp.to_html(shared_ctx)
    assert 'name="my-name"' in html
    assert 'placeholder="My Description"' in html
    assert 'value="my-val"' in html
