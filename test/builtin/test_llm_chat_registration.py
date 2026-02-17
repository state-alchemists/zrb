import os
from unittest.mock import patch

from zrb.builtin.llm.chat_tool_policy import (
    _path_inside_parent,
    approve_if_path_inside_cwd,
    approve_if_path_inside_journal_dir,
)


def test_is_path_inside_cwd():
    cwd = os.getcwd()
    assert _path_inside_parent(cwd, cwd)
    assert _path_inside_parent(os.path.join(cwd, "test_file.txt"), cwd)
    assert _path_inside_parent("~/", cwd) is False  # Expanduser test
    # Test path outside CWD
    parent_dir = os.path.dirname(cwd)
    if parent_dir != cwd:  # Not at root
        assert _path_inside_parent(parent_dir, cwd) is False


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

    # Test no path arguments (should return False when no path info)
    assert approve_if_path_inside_cwd({}) is False


def test_approve_if_path_inside_journal_dir():
    # Mock the CFG.LLM_JOURNAL_DIR
    mock_journal_dir = "/mock/journal/dir"
    
    with patch('zrb.builtin.llm.chat_tool_policy.CFG') as mock_cfg:
        mock_cfg.LLM_JOURNAL_DIR = mock_journal_dir
        
        # Test 'path' argument inside journal dir
        assert approve_if_path_inside_journal_dir({"path": mock_journal_dir}) is True
        assert approve_if_path_inside_journal_dir({"path": os.path.join(mock_journal_dir, "note.md")}) is True
        
        # Test 'path' argument outside journal dir
        assert approve_if_path_inside_journal_dir({"path": "/some/other/dir"}) is False
        
        # Test 'paths' argument
        assert approve_if_path_inside_journal_dir({
            "paths": [mock_journal_dir, os.path.join(mock_journal_dir, "note.md")]
        }) is True
        assert approve_if_path_inside_journal_dir({
            "paths": [mock_journal_dir, "/some/other/dir"]
        }) is False
        
        # Test no path arguments (should return False when no path info)
        assert approve_if_path_inside_journal_dir({}) is False
