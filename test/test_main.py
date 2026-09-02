import sys

from zrb.__main__ import serve_cli


def test_a_broken_init_script_reports_file_line_and_type_but_still_runs(
    tmp_path, capsys, monkeypatch
):
    """A broken `zrb_init.py` is never hidden, but it is not fatal: the CLI
    still starts with whatever partial state resulted, since a user who can
    see the error and still run zrb can fix it and rerun."""
    broken = tmp_path / "zrb_init.py"
    broken.write_text("this_name_does_not_exist()\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["zrb"])
    serve_cli()  # does not raise SystemExit — the CLI still runs
    captured = capsys.readouterr()
    assert "zrb_init.py" in captured.err
    assert "NameError" in captured.err
    # cli.run([]) with no subcommand prints the group/task listing to stdout —
    # proof startup actually continued past the broken init script.
    assert "GROUPS" in captured.out
