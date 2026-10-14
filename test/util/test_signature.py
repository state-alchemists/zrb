import builtins

from zrb.util.signature import can_take_positional


def test_counts_positional_parameters():
    assert can_take_positional(lambda a, b: None, 2, if_unknown=False)
    assert not can_take_positional(lambda a: None, 2, if_unknown=True)


def test_var_positional_takes_any_count():
    assert can_take_positional(lambda *args: None, 2, if_unknown=False)


def test_keyword_only_parameters_do_not_count():
    assert not can_take_positional(lambda a, *, b: None, 2, if_unknown=True)


def test_uninspectable_callable_answers_if_unknown():
    uninspectable = builtins.__build_class__  # no retrievable signature
    assert can_take_positional(uninspectable, 2, if_unknown=True)
    assert not can_take_positional(uninspectable, 2, if_unknown=False)
