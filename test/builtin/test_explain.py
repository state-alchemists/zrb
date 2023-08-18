from zrb.builtin.explain import (
    explain_dry, explain_kiss, explain_yagni, explain_solid,
    explain_zen_of_python
)


def test_explain_dry():
    function = explain_dry.to_function()
    result = function()
    assert result is None


def test_explain_kiss():
    function = explain_kiss.to_function()
    result = function()
    assert result is None


def test_explain_solid():
    function = explain_solid.to_function()
    result = function()
    assert result is None


def test_explain_yagni():
    function = explain_yagni.to_function()
    result = function()
    assert result is None


def test_explain_zen_of_python():
    function = explain_zen_of_python.to_function()
    result = function()
    assert result is None
