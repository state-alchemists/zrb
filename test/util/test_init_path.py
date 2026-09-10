import os

from zrb.util.init_path import get_init_path_list

# A name unlikely to already exist in any real ancestor directory, so results
# aren't polluted by a stray zrb_init.py somewhere above the test tmp dir.
_INIT_NAME = "zrb_init_path_test_marker.py"


def test_get_init_path_list_collects_files_root_to_cwd_in_order(tmp_path, monkeypatch):
    monkeypatch.setenv("ZRB_INIT_FILE_NAME", _INIT_NAME)

    grandparent = tmp_path / "a"
    parent = grandparent / "b"
    leaf = parent / "c"
    leaf.mkdir(parents=True)

    (tmp_path / _INIT_NAME).write_text("# top")
    (parent / _INIT_NAME).write_text("# parent, skips grandparent")
    # No init file directly in `leaf` or `grandparent`.

    monkeypatch.chdir(leaf)

    result = get_init_path_list()

    assert result == [
        os.path.join(str(tmp_path), _INIT_NAME),
        os.path.join(str(parent), _INIT_NAME),
    ]


def test_get_init_path_list_returns_empty_when_none_found(tmp_path, monkeypatch):
    monkeypatch.setenv("ZRB_INIT_FILE_NAME", _INIT_NAME)
    leaf = tmp_path / "x" / "y"
    leaf.mkdir(parents=True)
    monkeypatch.chdir(leaf)

    assert get_init_path_list() == []


def test_get_init_path_list_includes_cwd_itself(tmp_path, monkeypatch):
    monkeypatch.setenv("ZRB_INIT_FILE_NAME", _INIT_NAME)
    (tmp_path / _INIT_NAME).write_text("# cwd itself")
    monkeypatch.chdir(tmp_path)

    assert get_init_path_list() == [os.path.join(str(tmp_path), _INIT_NAME)]


def test_get_init_path_list_respects_configured_file_name(tmp_path, monkeypatch):
    monkeypatch.setenv("ZRB_INIT_FILE_NAME", "custom_init_marker.py")
    (tmp_path / "custom_init_marker.py").write_text("# custom name")
    (tmp_path / _INIT_NAME).write_text("# wrong name, must be ignored")
    monkeypatch.chdir(tmp_path)

    assert get_init_path_list() == [
        os.path.join(str(tmp_path), "custom_init_marker.py")
    ]
