import os

from zrb.builtin.setup.config_file_helper import append_config_block_if_missing


def test_append_config_block_if_missing_creates_file(tmp_path):
    file_path = str(tmp_path / "profile")

    appended = append_config_block_if_missing(file_path, "export FOO=bar")

    assert appended is True
    assert os.path.isfile(file_path)
    with open(file_path) as f:
        assert "export FOO=bar" in f.read()


def test_append_config_block_if_missing_appends_once(tmp_path):
    file_path = str(tmp_path / "profile")
    with open(file_path, "w") as f:
        f.write("existing content\n")

    first = append_config_block_if_missing(file_path, "export FOO=bar")
    second = append_config_block_if_missing(file_path, "export FOO=bar")

    assert first is True
    assert second is False
    with open(file_path) as f:
        content = f.read()
    assert content.count("export FOO=bar") == 1
    assert "existing content" in content


def test_append_config_block_if_missing_preserves_existing_content(tmp_path):
    file_path = str(tmp_path / "profile")
    with open(file_path, "w") as f:
        f.write("line one\nline two")

    append_config_block_if_missing(file_path, "export FOO=bar")

    with open(file_path) as f:
        content = f.read()
    assert "line one" in content
    assert "line two" in content
    assert "export FOO=bar" in content
