from zrb.builtin.principle import (
    show_dry_principle, show_kiss_principle,
    show_solid_principle, show_yagni_principle
)


def test_show_dry_principle():
    function = show_dry_principle.to_function()
    result = function()
    assert result is None


def test_show_kiss_principle():
    function = show_kiss_principle.to_function()
    result = function()
    assert result is None


def test_show_solid_principle():
    function = show_solid_principle.to_function()
    result = function()
    assert result is None


def test_show_yagni_principle():
    function = show_yagni_principle.to_function()
    result = function()
    assert result is None
