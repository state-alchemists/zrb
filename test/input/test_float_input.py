import pytest

from zrb.context.shared_context import SharedContext
from zrb.input.float_input import FloatInput


def test_float_input_to_html():
    float_input = FloatInput(
        name="my_float",
        description="My float input",
        default=1.23,
    )
    shared_ctx = SharedContext(env={})
    html = float_input.to_html(shared_ctx)
    assert 'type="number"' in html
    assert 'name="my_float"' in html
    assert 'placeholder="My float input"' in html
    assert 'value="1.23"' in html
    assert 'step="any"' in html


def test_float_input_get_default_str():
    float_input = FloatInput(name="my_float", default=4.56)
    shared_ctx = SharedContext(env={})
    default_str = float_input.get_default_str(shared_ctx)
    assert default_str == "4.56"


def test_float_input_parse_str_value():
    float_input = FloatInput(name="my_float")
    shared_ctx = SharedContext()
    float_input.update_shared_context(shared_ctx, str_value="7.89")
    value = shared_ctx.input.my_float
    assert value == 7.89
    assert isinstance(value, float)


def test_float_input_rejected_value_names_the_flag_and_the_accepted_shape():
    float_input = FloatInput(name="ratio")
    with pytest.raises(ValueError) as excinfo:
        float_input.update_shared_context(SharedContext(), str_value="abc")
    message = str(excinfo.value)
    assert "'ratio'" in message
    assert "'abc'" in message
    assert "a number" in message
    assert "could not convert" not in message
