import os

from zrb.builtin.llm.chat_tool_policy import (
    _is_path_inside_cwd,
    approve_if_path_inside_cwd,
)


def test_is_path_inside_cwd():
    cwd = os.getcwd()
    assert _is_path_inside_cwd(cwd)
    assert _is_path_inside_cwd(os.path.join(cwd, "test_file.txt"))
    assert _is_path_inside_cwd("~/") is False  # Expanduser test
    # Test path outside CWD
    parent_dir = os.path.dirname(cwd)
    if parent_dir != cwd:  # Not at root
        assert _is_path_inside_cwd(parent_dir) is False


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
