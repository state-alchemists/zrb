import textwrap

from zrb.util.codemod.modify_function_call import (
    append_param_to_function_call,
    prepend_param_to_function_call,
    replace_function_call_param,
)

original_code = "existing_function(5)"


def test_replace_function_call_param():
    new_code = replace_function_call_param(original_code, "existing_function", "4")
    assert new_code == textwrap.dedent("existing_function(4)")


def test_prepend_param_to_function_call():
    new_code = prepend_param_to_function_call(original_code, "existing_function", "4")
    assert new_code == textwrap.dedent("existing_function(4, 5)")


def test_append_param_to_function_call():
    new_code = append_param_to_function_call(original_code, "existing_function", "4")
    assert new_code == textwrap.dedent("existing_function(5, 4)")
