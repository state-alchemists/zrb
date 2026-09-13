from zrb.util.exception import exception_summary


def test_exception_summary_never_empty_for_bare_raise():
    assert exception_summary(ValueError()) == "ValueError"
    assert exception_summary(RuntimeError()) == "RuntimeError"


def test_exception_summary_prefixes_type_name():
    assert exception_summary(ValueError("boom")) == "ValueError: boom"


def test_exception_summary_avoids_duplicated_type_name():
    assert exception_summary(ValueError("ValueError: boom")) == "ValueError: boom"


def test_exception_summary_two_arguments_uses_str():
    # str() of a multi-arg exception is the tuple repr
    assert exception_summary(ValueError("a", "b")) == "ValueError: ('a', 'b')"


def test_exception_summary_accepts_complex_exception():
    assert exception_summary(KeyError("missing")) == "KeyError: 'missing'"
