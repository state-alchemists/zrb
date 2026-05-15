import os

from zrb.builtin.llm.chat_tool_policy import approve_if_path_inside_cwd


def test_approve_if_path_inside_cwd():
    cwd = os.getcwd()
    # Test 'path' argument
    assert approve_if_path_inside_cwd({"path": cwd}) is True
    assert approve_if_path_inside_cwd({"path": os.path.dirname(cwd)}) is False

    # Tool args without a path key are not gated by this helper
    assert approve_if_path_inside_cwd({}) is True
