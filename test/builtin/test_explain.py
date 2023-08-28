from zrb.builtin.explain import (
    explain_dry_principle, explain_kiss_principle, explain_yagni_principle,
    explain_solid_principle, explain_zen_of_python
)


def test_explain_dry():
    function = explain_dry_principle.to_function()
    result = function()
    assert result is None


def test_explain_kiss():
    function = explain_kiss_principle.to_function()
    result = function()
    assert result is None


def test_explain_solid():
    function = explain_solid_principle.to_function()
    result = function()
    assert result is None


def test_explain_yagni():
    function = explain_yagni_principle.to_function()
    result = function()
    assert result is None


def test_explain_zen_of_python():
    function = explain_zen_of_python.to_function()
    result = function()
    assert result is None
