import pytest

from zrb.input.base_input import BaseInput


class ConcreteInput(BaseInput):
    def to_html(self) -> str:
        return "<input>"

    def get_default_str(self) -> str:
        return str(self._default_value)

    def parse_str_value(self, value: str):
        return value


def test_base_input_basic():
    # BaseInput(self, name, description=None, prompt=None, default="", ...)
    inp = ConcreteInput("my-input", "Desc", prompt="Prompt", default="val")
    assert inp.name == "my-input"
    assert inp.description == "Desc"
    assert inp._default_value == "val"
    assert inp.to_html() == "<input>"


def test_base_input_always_prompt():
    inp1 = ConcreteInput("i1", always_prompt=True)
    inp2 = ConcreteInput("i2", always_prompt=False)
    assert inp1.always_prompt is True
    assert inp2.always_prompt is False


def test_base_input_allow_empty():
    inp1 = ConcreteInput("i1", allow_empty=True)
    inp2 = ConcreteInput("i2", allow_empty=False)
    # allow_empty is not a property but an internal attribute _allow_empty
    assert inp1._allow_empty is True
    assert inp2._allow_empty is False
