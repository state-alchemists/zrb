import sys

import pytest

from zrb.__main__ import serve_cli


def test_a_broken_init_script_aborts_with_file_line_and_type(
    tmp_path, capsys, monkeypatch
):
    broken = tmp_path / "zrb_init.py"
    broken.write_text("this_name_does_not_exist()\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["zrb"])
    with pytest.raises(SystemExit) as excinfo:
        serve_cli()
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "zrb_init.py" in err
    assert "NameError" in err
