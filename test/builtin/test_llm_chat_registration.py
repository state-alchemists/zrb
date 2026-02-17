import os

from zrb.builtin.llm.chat_tool_policy import approve_if_path_inside_cwd


def test_approve_if_path_inside_cwd():
    cwd = os.getcwd()
    # Test 'path' argument
    assert approve_if_path_inside_cwd({"path": cwd}) is True
    assert approve_if_path_inside_cwd({"path": os.path.dirname(cwd)}) is False

    # Test 'paths' argument
    assert (
        approve_if_path_inside_cwd({"paths": [cwd, os.path.join(cwd, "abc")]}) is True
    )
    assert approve_if_path_inside_cwd({"paths": [cwd, os.path.dirname(cwd)]}) is False
    assert approve_if_path_inside_cwd({"paths": "not a list"}) is False

    # Test no path arguments
    assert approve_if_path_inside_cwd({}) is True
