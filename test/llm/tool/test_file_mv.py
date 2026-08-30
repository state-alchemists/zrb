import os

import pytest

from zrb.llm.tool.file_mv import move_file
from zrb.llm.tool.file_observation import clear_observed
from zrb.llm.tool.file_read import read_file


@pytest.fixture(autouse=True)
def _reset_observed_state():
    """The overwrite-destination check (file_observation.py) is run-scoped
    module state — reset it so one test's Read never leaks into another's."""
    clear_observed()
    yield
    clear_observed()


@pytest.fixture
def temp_dir(tmp_path):
    d = tmp_path / "test_mv"
    d.mkdir()
    return str(d)


def test_move_file(temp_dir):
    src = os.path.join(temp_dir, "src.txt")
    dst = os.path.join(temp_dir, "dst.txt")
    open(src, "w").close()
    result = move_file(src, dst)
    assert "Moved" in result
    assert not os.path.exists(src)
    assert os.path.exists(dst)


def test_rename_file(temp_dir):
    src = os.path.join(temp_dir, "old.txt")
    dst = os.path.join(temp_dir, "new.txt")
    with open(src, "w") as f:
        f.write("content")
    result = move_file(src, dst)
    assert "Moved" in result
    with open(dst) as f:
        assert f.read() == "content"


def test_move_file_creates_parent_dirs(temp_dir):
    src = os.path.join(temp_dir, "src.txt")
    dst = os.path.join(temp_dir, "nested", "deep", "dst.txt")
    open(src, "w").close()
    result = move_file(src, dst)
    assert "Moved" in result
    assert os.path.exists(dst)


def test_move_directory(temp_dir):
    src = os.path.join(temp_dir, "srcdir")
    os.mkdir(src)
    open(os.path.join(src, "file.txt"), "w").close()
    dst = os.path.join(temp_dir, "dstdir")
    result = move_file(src, dst)
    assert "Moved" in result
    assert not os.path.exists(src)
    assert os.path.exists(os.path.join(dst, "file.txt"))


def test_move_nonexistent_source(temp_dir):
    src = os.path.join(temp_dir, "ghost.txt")
    dst = os.path.join(temp_dir, "dst.txt")
    result = move_file(src, dst)
    assert "Error" in result
    assert "not found" in result


def test_move_onto_unread_existing_destination_is_refused(temp_dir):
    src = os.path.join(temp_dir, "src.txt")
    dst = os.path.join(temp_dir, "dst.txt")
    with open(src, "w") as f:
        f.write("new")
    with open(dst, "w") as f:
        f.write("old")
    result = move_file(src, dst)
    assert "has not been read or listed in this session" in result
    assert os.path.exists(src)
    with open(dst) as f:
        assert f.read() == "old"


def test_move_onto_read_existing_destination_succeeds(temp_dir):
    src = os.path.join(temp_dir, "src.txt")
    dst = os.path.join(temp_dir, "dst.txt")
    with open(src, "w") as f:
        f.write("new")
    with open(dst, "w") as f:
        f.write("old")
    read_file(dst)
    result = move_file(src, dst)
    assert "Moved" in result
    with open(dst) as f:
        assert f.read() == "new"


def test_move_onto_unlisted_existing_directory_is_refused(temp_dir):
    src = os.path.join(temp_dir, "src.txt")
    dst = os.path.join(temp_dir, "existingdir")
    os.mkdir(dst)
    with open(src, "w") as f:
        f.write("content")
    result = move_file(src, dst)
    assert "has not been read or listed in this session" in result
    assert os.path.exists(src)


def test_move_onto_listed_existing_directory_nests_source_inside_it(temp_dir):
    from zrb.llm.tool.file_list import list_files

    src = os.path.join(temp_dir, "src.txt")
    dst = os.path.join(temp_dir, "existingdir")
    os.mkdir(dst)
    with open(src, "w") as f:
        f.write("content")
    list_files(dst)
    result = move_file(src, dst)
    assert "Moved" in result
    assert not os.path.exists(src)
    with open(os.path.join(dst, "src.txt")) as f:
        assert f.read() == "content"


def test_move_onto_unread_existing_binary_destination_is_refused(temp_dir):
    src = os.path.join(temp_dir, "src.txt")
    dst = os.path.join(temp_dir, "dst.bin")
    with open(src, "w") as f:
        f.write("new")
    with open(dst, "wb") as f:
        f.write(b"\xff\xfe\x00binary")
    result = move_file(src, dst)
    assert "has not been read or listed in this session" in result
    assert os.path.exists(src)


def test_move_onto_listed_existing_binary_destination_succeeds(temp_dir):
    from zrb.llm.tool.file_list import list_files

    src = os.path.join(temp_dir, "src.txt")
    dst = os.path.join(temp_dir, "dst.bin")
    with open(src, "w") as f:
        f.write("new")
    with open(dst, "wb") as f:
        f.write(b"\xff\xfe\x00binary")
    list_files(temp_dir)
    result = move_file(src, dst)
    assert "Moved" in result
    with open(dst, "rb") as f:
        assert f.read() == b"new"


def test_move_records_destination_as_seen_for_immediate_followup(temp_dir):
    from zrb.llm.tool.file_rm import remove_file

    src = os.path.join(temp_dir, "src.txt")
    dst = os.path.join(temp_dir, "dst.txt")
    with open(src, "w") as f:
        f.write("content")
    move_file(src, dst)
    result = remove_file(dst)
    assert "Removed" in result
