import json
import os

import pytest

from zrb.llm.note.manager import NoteManager


@pytest.fixture
def temp_note_file(tmp_path):
    f = tmp_path / "notes.json"
    return str(f)


def test_note_manager_write_read(temp_note_file):
    manager = NoteManager(temp_note_file)
    manager.write("/tmp/test", "content 1")
    assert manager.read("/tmp/test") == "content 1"


def test_note_manager_read_all(temp_note_file):
    manager = NoteManager(temp_note_file)
    manager.write("/", "root note")
    manager.write("/tmp", "tmp note")
    manager.write("/tmp/test", "test note")

    notes = manager.read_all("/tmp/test")
    assert notes["/"] == "root note"
    assert notes["/tmp"] == "tmp note"
    assert notes["/tmp/test"] == "test note"


def test_note_manager_normalized_path():
    manager = NoteManager()
    home = os.path.expanduser("~")
    assert manager._get_normalized_path(home) == "~"
    assert manager._get_normalized_path(os.path.join(home, "abc")) == os.path.join(
        "~", "abc"
    )


def test_note_manager_load_invalid_json(temp_note_file):
    with open(temp_note_file, "w") as f:
        f.write("invalid json")
    manager = NoteManager(temp_note_file)
    assert manager._load_data() == {}
